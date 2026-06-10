import django_rq
from core.models import ExecutionJob
from core.services.rq_jobs import execute_submission_job
import uuid
from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import requests
import json
from django.db.models import Q
from .models import DailyQuestion, UserStreak, DailySubmission, TestCase
from core.services.execution_service import execution_service, ExecutionResult
from concurrent.futures import ThreadPoolExecutor

@login_required(login_url='login')
def daily_challenge(request):
    today = timezone.now().date()
    
    # 1. Get Today's Question
    question = DailyQuestion.objects.filter(release_date=today).first()
    
    # 2. Get User Streak Data
    streak_obj, created = UserStreak.objects.get_or_create(user=request.user)
    
    # Check if already solved
    already_solved = False
    submission = None
    if question:
        submission = DailySubmission.objects.filter(user=request.user, question=question).first()
        if submission:
            already_solved = True

    context = {
        'question': question,
        'streak': streak_obj,
        'already_solved': already_solved,
        'submission': submission
    }
    return render(request, 'challenges/daily_challenge.html', context)

@login_required
def submit_mcq(request, question_id):
    if request.method == "POST":
        question = get_object_or_404(DailyQuestion, id=question_id)
        selected_option = request.POST.get('option')
        
        # Calculate Score
        score = 5 if selected_option == question.correct_option else 0
        
        # Save & Update Streak
        update_user_progress(request.user, question, score)
        
        if score > 0:
            messages.success(request, f"Correct! You earned 5 points.")
        else:
            messages.error(request, f"Incorrect. The correct answer was {question.correct_option}.")
            
    return redirect('daily_challenge')

@login_required
def submit_code(request, question_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_code = data.get('code')
            language = data.get('language')
            
            question = get_object_or_404(DailyQuestion, id=question_id)
            test_cases = question.test_cases.all()
            
            total_cases = test_cases.count()
            if total_cases == 0:
                return render(request, 'challenges/code_result_partial.html', {
                    'score': 0,
                    'results': [],
                    'total': 0,
                    'error': 'No test cases configured.'
                })

            passed_cases = 0
            results = []

            # Run test cases synchronously in parallel (bypasses Redis/RQ worker on AWS App Runner)
            from assessments.views import run_code_piston
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(run_code_piston, user_code, language, test.input_data)
                    for test in test_cases
                ]
                for i, future in enumerate(futures):
                    test = test_cases[i]
                    try:
                        actual_output = future.result(timeout=15)
                        clean_actual = actual_output.strip()
                        clean_expected = test.expected_output.strip()
                        
                        passed = (clean_actual == clean_expected)
                        if passed:
                            passed_cases += 1
                        results.append(passed)
                    except Exception:
                        results.append(False)

            # Update Streak/XP only if all test cases passed
            if passed_cases == total_cases:
                update_user_progress(request.user, question, 5)

            return render(request, 'challenges/code_result_partial.html', {
                'score': passed_cases, 
                'results': results,
                'total': total_cases
            })

        except Exception as e:
            # Handle JSON errors or other unexpected crashes
            return render(request, 'challenges/code_result_partial.html', {
                'score': 0,
                'results': [],
                'total': 0,
                'error': str(e)
            })

def update_user_progress(user, question, score):
    # 1. Prevent Duplicate Submission
    if DailySubmission.objects.filter(user=user, question=question).exists():
        return # Already submitted

    # 2. Record Submission
    DailySubmission.objects.create(user=user, question=question, score=score)

    # 3. Update Streak & Total Score
    streak_obj, _ = UserStreak.objects.get_or_create(user=user)
    streak_obj.total_score += score
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    if streak_obj.last_solved_date == yesterday:
        # Continued Streak
        streak_obj.current_streak += 1
    elif streak_obj.last_solved_date != today:
        # Broken Streak (or first time)
        streak_obj.current_streak = 1
    
    # Update Max Streak
    if streak_obj.current_streak > streak_obj.max_streak:
        streak_obj.max_streak = streak_obj.current_streak
    
    streak_obj.last_solved_date = today
    streak_obj.save()

def leaderboard(request):
    # Sort by Score (Desc), then Streak (Desc)
    leaders = UserStreak.objects.select_related('user').order_by('-total_score', '-current_streak')[:20]
    
    user_rank = None
    user_streak = None
    
    if request.user.is_authenticated:
        try:
            user_streak = UserStreak.objects.get(user=request.user)
            # Count how many users have a strictly higher score, OR same score but better streak
            user_rank = UserStreak.objects.filter(
                Q(total_score__gt=user_streak.total_score) |
                Q(total_score=user_streak.total_score, current_streak__gt=user_streak.current_streak)
            ).count() + 1
        except UserStreak.DoesNotExist:
            pass
            
    return render(request, 'challenges/leaderboard.html', {
        'leaders': leaders,
        'user_rank': user_rank,
        'user_streak': user_streak
    })
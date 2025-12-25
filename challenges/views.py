from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import requests
import json
from .models import DailyQuestion, UserStreak, DailySubmission, TestCase

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
        data = json.loads(request.body)
        user_code = data.get('code')
        language = data.get('language')
        
        question = get_object_or_404(DailyQuestion, id=question_id)
        test_cases = question.test_cases.all()
        
        score = 0
        total_cases = test_cases.count()
        results = []

        # Run against Piston for every test case
        for test in test_cases:
            payload = {
                "language": language, 
                "version": "3.10.0", # Simplified version mapping for now
                "files": [{"content": user_code}],
                "stdin": test.input_data
            }
            
            try:
                # Call Piston API
                resp = requests.post('https://emkc.org/api/v2/piston/execute', json=payload)
                api_out = resp.json().get('run', {}).get('output', '').strip()
                expected = test.expected_output.strip()
                
                if api_out == expected:
                    score += 1
                    results.append(True)
                else:
                    results.append(False)
            except:
                results.append(False)

        # Update Streak
        update_user_progress(request.user, question, score)
        
        return render(request, 'challenges/code_result_partial.html', {
            'score': score, 
            'results': results,
            'total': total_cases
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
    return render(request, 'challenges/leaderboard.html', {'leaders': leaders})
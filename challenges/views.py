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
from core.execution_queue import enqueue_execution_job
from core.models import ExecutionJob
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
            # Enqueue async job for code execution (practice queue)
            job = enqueue_execution_job(
                job_type='practice',
                user=request.user,
                code=user_code,
                language=language,
                input_data='',
                related_id=str(question.id),
                queue_name='practice',
            )
            return JsonResponse({'status': 'queued', 'job_id': str(job.id)})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

@require_GET
@login_required
def job_status(request):
    """API endpoint to poll job status/result by job_id (for async execution)."""
    job_id = request.GET.get('job_id')
    if not job_id:
        return JsonResponse({'status': 'error', 'error': 'Missing job_id'}, status=400)
    try:
        job = ExecutionJob.objects.get(id=job_id)
        # Security: Only allow owner to poll their own job
        if job.user and job.user != request.user:
            return JsonResponse({'status': 'error', 'error': 'Unauthorized'}, status=403)
        # If job is not associated with a user, deny access (or allow only for public jobs if needed)
        if not job.user:
            return JsonResponse({'status': 'error', 'error': 'Unauthorized'}, status=403)
        return JsonResponse({
            'status': job.status,
            'result': job.result if job.status == 'completed' else None,
            'error': job.error if job.status in ['failed', 'timeout', 'cancelled'] else '',
            'job_id': str(job.id),
        })
    except ExecutionJob.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Job not found'}, status=404)

def update_user_progress(user, question, score):
    from django.db import transaction
    with transaction.atomic():
        # 1. Prevent Duplicate Submission (atomic check)
        if DailySubmission.objects.select_for_update().filter(user=user, question=question).exists():
            return # Already submitted

        # 2. Record Submission
        DailySubmission.objects.create(user=user, question=question, score=score)

        # 3. Update Streak & Total Score
        streak_obj, _ = UserStreak.objects.select_for_update().get_or_create(user=user)
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
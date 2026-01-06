from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
import json
import requests # For Piston API
from .models import Exam, ExamQuestion, StudentExamAttempt, Topic

@login_required
def start_exam(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    exam = topic.exam
    
    # Create or Get Attempt
    attempt, created = StudentExamAttempt.objects.get_or_create(
        user=request.user, 
        exam=exam,
        completed_at__isnull=True # Get active attempt
    )
    
    context = {
        'exam': exam,
        'questions': exam.questions.all(),
        'attempt': attempt,
        'attempt_id': attempt.id
    }
    return render(request, 'assessments/take_exam.html', context)
# assessments/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
import json
from .models import Exam, StudentExamAttempt, ExamQuestion

# ... keep start_exam and check_code ...

@login_required
def submit_exam(request, attempt_id):
    if request.method == "POST":
        attempt = get_object_or_404(StudentExamAttempt, id=attempt_id, user=request.user)
        
        # If already completed, prevent re-submission logic
        if attempt.completed_at:
            return JsonResponse({'status': 'success', 'redirect_url': f'/assessments/result/{attempt.id}/'})

        data = json.loads(request.body)
        answers = data.get('answers', {})
        warnings = data.get('warnings', 0)
        
        total_score = 0
        
        # Grading Logic
        for q_id, user_ans in answers.items():
            try:
                question = ExamQuestion.objects.get(id=q_id)
                
                # 1. MCQ Single
                if question.q_type == 'MCQ_SINGLE':
                    if str(user_ans) == str(question.correct_options):
                        total_score += question.marks
                
                # 2. MCQ Multi
                elif question.q_type == 'MCQ_MULTI':
                    if not question.correct_options: continue
                    correct_set = set(str(question.correct_options).split(','))
                    # Handle if user sent list or single value
                    user_val_list = user_ans if isinstance(user_ans, list) else [user_ans]
                    user_set = set(map(str, user_val_list))
                    
                    if correct_set == user_set:
                        total_score += question.marks

                # 3. Coding (Simple Scoring based on submission or generic logic)
                elif question.q_type == 'CODE':
                    # In a real app, you might want to re-run test cases here to verify
                    # For now, we assume the client-side check or previous check was valid
                    # Or give full marks if they wrote something substantial (Mock Logic)
                    if user_ans.get('code') and len(user_ans.get('code')) > 10:
                        # You can improve this by storing "passed_cases" in the frontend answer payload
                        total_score += question.marks 

            except ExamQuestion.DoesNotExist:
                continue

        # Save Attempt
        attempt.score = total_score
        attempt.response_data = answers # <--- SAVE ANSWERS HERE
        attempt.completed_at = timezone.now()
        attempt.warnings_triggered = warnings
        attempt.passed = total_score >= (attempt.exam.total_marks * (attempt.exam.pass_percentage / 100))
        attempt.save()
        
        # Return URL to redirect
        return JsonResponse({
            'status': 'success', 
            'redirect_url': f'/assessments/result/{attempt.id}/'
        })

@login_required
def exam_history(request):
    """List all previous exams taken by the user"""
    attempts = StudentExamAttempt.objects.filter(user=request.user, completed_at__isnull=False).order_by('-completed_at')
    return render(request, 'assessments/exam_history.html', {'attempts': attempts})

@login_required
def attempt_detail(request, attempt_id):
    """Detailed Report Card"""
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id, user=request.user)
    questions = attempt.exam.questions.all()
    user_responses = attempt.response_data
    
    report = []
    
    for q in questions:
        user_ans = user_responses.get(str(q.id))
        is_correct = False
        correct_display = q.correct_options
        user_display = user_ans

        # Format Display Data
        if q.q_type == 'MCQ_SINGLE':
            # Map option ID to Text
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            correct_display = options.get(str(q.correct_options), "N/A")
            user_display = options.get(str(user_ans), "Not Attempted")
            if str(user_ans) == str(q.correct_options): is_correct = True
            
        elif q.q_type == 'MCQ_MULTI':
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            # Format Correct
            c_opts = str(q.correct_options).split(',')
            correct_display = ", ".join([options.get(o, o) for o in c_opts])
            
            # Format User
            if user_ans:
                u_opts = user_ans if isinstance(user_ans, list) else [user_ans]
                user_display = ", ".join([options.get(str(o), str(o)) for o in u_opts])
                # Check correctness
                if set(c_opts) == set(map(str, u_opts)): is_correct = True
            else:
                user_display = "Not Attempted"

        elif q.q_type == 'CODE':
            is_correct = None # Scoring for code is complex to display as boolean
            user_display = user_ans.get('code') if user_ans else "No Code"
            correct_display = "N/A (Coding Challenge)"

        report.append({
            'question': q,
            'user_answer': user_display,
            'correct_answer': correct_display,
            'is_correct': is_correct,
            'type': q.q_type
        })

    return render(request, 'assessments/attempt_detail.html', {
        'attempt': attempt, 
        'report': report
    })

def run_code_piston(code, lang, stdin):
    # Reuse your existing Piston logic here
    # Return stdout string
    try:
        payload = {
            "language": lang,
            "version": "3.10.0",
            "files": [{"content": code}],
            "stdin": stdin
        }
        resp = requests.post('https://emkc.org/api/v2/piston/execute', json=payload)
        return resp.json().get('run', {}).get('output', '').strip()
    except:
        return ""


# assessments/views.py

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
import requests
from .models import ExamQuestion

# ... keep start_exam and submit_exam ...

# Reuse your Piston logic or import it
def run_code_piston(code, lang, stdin):
    try:
        payload = {
            "language": lang,
            "version": "3.10.0",
            "files": [{"content": code}],
            "stdin": stdin
        }
        resp = requests.post('https://emkc.org/api/v2/piston/execute', json=payload)
        return resp.json().get('run', {}).get('output', '').strip()
    except:
        return ""

@login_required
def check_code(request, question_id):
    """
    Runs code against hidden test cases for a specific question inside the exam.
    """
    if request.method == "POST":
        data = json.loads(request.body)
        code = data.get('code')
        language = data.get('language', 'python')
        
        question = get_object_or_404(ExamQuestion, id=question_id)
        test_cases = question.test_cases.all()
        
        passed_count = 0
        total_cases = test_cases.count()
        
        if total_cases == 0:
            return JsonResponse({'status': 'error', 'message': 'No test cases found.'})

        # Run against all test cases
        for case in test_cases:
            output = run_code_piston(code, language, case.input_data)
            if output == case.expected_output.strip():
                passed_count += 1
        
        all_passed = (passed_count == total_cases)
        
        return JsonResponse({
            'status': 'success',
            'passed_count': passed_count,
            'total_cases': total_cases,
            'all_passed': all_passed
        })
        
    return JsonResponse({'status': 'error'}, status=400)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
import json
import requests 
from .models import Exam, ExamSection, ExamQuestion, StudentExamAttempt, Topic

# --- HELPER: Code Execution ---
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

# --- VIEWS ---

# In assessments/views.py

@login_required
def start_exam(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    try:
        exam = topic.exam
    except Exam.DoesNotExist:
        return render(request, 'error.html', {'message': 'No exam found for this topic.'})

    attempt, created = StudentExamAttempt.objects.get_or_create(
        user=request.user, 
        exam=exam,
        completed_at__isnull=True 
    )

    # 1. Initialize Section if needed
    if created or not attempt.current_section:
        first_section = exam.sections.order_by('order').first()
        if not first_section:
            return render(request, 'error.html', {'message': 'Exam configuration error: No sections found.'})
        attempt.current_section = first_section
        attempt.section_start_time = timezone.now()
        attempt.save()

    # 2. Calculate Time Left
    elapsed = (timezone.now() - attempt.section_start_time).total_seconds()
    duration_sec = attempt.current_section.duration_minutes * 60
    time_left = max(0, duration_sec - elapsed)

    if time_left == 0:
         return redirect('submit_section', attempt_id=attempt.id)

    # 3. CHECK IF LAST SECTION (CRITICAL FIX)
    # We check if there are any sections with a higher order than the current one
    next_section_exists = ExamSection.objects.filter(
        exam=exam, 
        order__gt=attempt.current_section.order
    ).exists()

    context = {
        'exam': exam,
        'section': attempt.current_section,
        'questions': attempt.current_section.questions.all(),
        'attempt': attempt,
        'time_left': int(time_left),
        'total_sections': exam.sections.count(),
        'current_section_index': list(exam.sections.order_by('order')).index(attempt.current_section) + 1,
        'is_last_section': not next_section_exists,  # <--- PASS THIS TO TEMPLATE
    }
    return render(request, 'assessments/take_section_exam.html', context)


# In assessments/views.py

@login_required
def submit_section(request, attempt_id):
    """
    Handles submission of a SINGLE section.
    POST: User clicks "Next/Submit" with answers.
    GET:  System forces submission (Time Expired).
    """
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id, user=request.user)
    current_section = attempt.current_section
    
    # Safety Check: If no active section, just go to dashboard or result
    if not current_section:
        if attempt.completed_at:
             return redirect('attempt_detail', attempt_id=attempt.id)
        return redirect('dashboard')

    # 1. Parse Answers based on Request Method
    new_answers = {}
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_answers = data.get('answers', {})
        except json.JSONDecodeError:
            pass # No answers provided
    
    # (If GET, new_answers remains empty {}, representing a forced timeout submission)

    # 2. Save Answers (Merge with existing)
    if not attempt.response_data:
        attempt.response_data = {}
    
    # Only update if we actually have new answers (POST), otherwise keep old ones
    if new_answers:
        attempt.response_data[str(current_section.id)] = new_answers
        attempt.save() # Save intermediate state
    
    # 3. Find Next Section
    next_section = ExamSection.objects.filter(
        exam=attempt.exam, 
        order__gt=current_section.order
    ).order_by('order').first()

    if next_section:
        # Move to next section
        attempt.current_section = next_section
        attempt.section_start_time = timezone.now() # Reset timer
        attempt.save()
        
        # If POST (AJAX), return JSON URL. If GET (Redirect), do a standard redirect.
        if request.method == "POST":
            return JsonResponse({
                'status': 'next_section', 
                'redirect_url': f'/assessments/start/{attempt.exam.topic.id}/'
            })
        else:
            return redirect('start_exam', topic_id=attempt.exam.topic.id)

    else:
        # FINISH EXAM
        attempt.completed_at = timezone.now()
        attempt.current_section = None # Clear active section
        attempt.save()
        
        # Calculate Final Score
        calculate_final_score(attempt)
        
        if request.method == "POST":
            return JsonResponse({
                'status': 'finished', 
                'redirect_url': f'/assessments/result/{attempt.id}/'
            })
        else:
            return redirect('attempt_detail', attempt_id=attempt.id)

def calculate_final_score(attempt):
    total_score = 0
    
    # response_data structure: { "sec_id": { "q_id": "ans" }, ... }
    # We flatten this to process easier, or loop through sections
    
    for section_id, section_answers in attempt.response_data.items():
        for q_id, user_ans in section_answers.items():
            try:
                question = ExamQuestion.objects.get(id=q_id)
                
                # Grading Logic (Same as before)
                if question.q_type == 'MCQ_SINGLE':
                    if str(user_ans) == str(question.correct_options):
                        total_score += question.marks
                
                elif question.q_type == 'MCQ_MULTI':
                    if not question.correct_options: continue
                    correct_set = set(str(question.correct_options).split(','))
                    user_val_list = user_ans if isinstance(user_ans, list) else [user_ans]
                    user_set = set(map(str, user_val_list))
                    
                    if correct_set == user_set:
                        total_score += question.marks
                
                elif question.q_type == 'CODE':
                    # Basic scoring: check if code exists and is substantial
                    if user_ans.get('code') and len(user_ans.get('code')) > 10:
                        total_score += question.marks
                        
            except ExamQuestion.DoesNotExist:
                continue

    attempt.score = total_score
    attempt.passed = total_score >= (attempt.exam.total_marks * (attempt.exam.pass_percentage / 100))
    attempt.save()


@login_required
def check_code(request, question_id):
    """
    Runs code against hidden test cases. 
    Can be used during the exam for 'Run/Check' buttons.
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
            return JsonResponse({'status': 'error', 'message': 'No test cases configured.'})

        for case in test_cases:
            output = run_code_piston(code, language, case.input_data)
            # Basic string comparison (trim whitespace)
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


@login_required
def exam_history(request):
    attempts = StudentExamAttempt.objects.filter(user=request.user, completed_at__isnull=False).order_by('-completed_at')
    return render(request, 'assessments/exam_history.html', {'attempts': attempts})


@login_required
def attempt_detail(request, attempt_id):
    """Detailed Report Card"""
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id, user=request.user)
    
    # Get all questions across all sections for this exam
    # Using 'sections__questions' lookup
    questions = ExamQuestion.objects.filter(section__exam=attempt.exam).order_by('section__order', 'id')
    
    # Flatten response data for easier lookup
    # Current structure: { "sec_1": {"q_1": "ans"}, "sec_2": ... }
    flat_answers = {}
    if attempt.response_data:
        for sec_data in attempt.response_data.values():
            flat_answers.update(sec_data)

    report = []
    
    for q in questions:
        user_ans = flat_answers.get(str(q.id))
        is_correct = False
        correct_display = q.correct_options
        user_display = user_ans

        # Display Logic
        if q.q_type == 'MCQ_SINGLE':
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            correct_display = options.get(str(q.correct_options), "N/A")
            user_display = options.get(str(user_ans), "Not Attempted")
            if str(user_ans) == str(q.correct_options): is_correct = True
            
        elif q.q_type == 'MCQ_MULTI':
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            c_opts = str(q.correct_options).split(',')
            correct_display = ", ".join([options.get(o, o) for o in c_opts])
            
            if user_ans:
                u_opts = user_ans if isinstance(user_ans, list) else [user_ans]
                user_display = ", ".join([options.get(str(o), str(o)) for o in u_opts])
                if set(c_opts) == set(map(str, u_opts)): is_correct = True
            else:
                user_display = "Not Attempted"

        elif q.q_type == 'CODE':
            is_correct = None 
            if isinstance(user_ans, dict):
                user_display = user_ans.get('code', "No Code")
            else:
                user_display = "No Code"
            correct_display = "N/A (Coding)"

        report.append({
            'question': q,
            'user_answer': user_display,
            'correct_answer': correct_display,
            'is_correct': is_correct,
            'type': q.q_type,
            'section_name': q.section.name # Useful for grouping in UI
        })

    return render(request, 'assessments/attempt_detail.html', {
        'attempt': attempt, 
        'report': report
    })
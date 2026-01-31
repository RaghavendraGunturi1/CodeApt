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
    try:
        attempt = get_object_or_404(StudentExamAttempt, id=attempt_id, user=request.user)
        current_section = attempt.current_section
        
        if attempt.completed_at:
            return redirect('attempt_detail', attempt_id=attempt.id)
        
        if not current_section:
            return redirect('dashboard')

        # 1. Parse Request Data
        new_answers = {}
        warnings = 0
        force_end_exam = False 

        if request.method == "POST":
            try:
                data = json.loads(request.body)
                new_answers = data.get('answers', {})
                warnings = int(data.get('warnings', 0)) # Ensure integer
                force_end_exam = data.get('force_end', False)
            except (json.JSONDecodeError, TypeError):
                print("Warning: Failed to parse JSON body")
        
        # 2. Safe JSON Field Handling (CRITICAL FIX)
        # Handle case where field is None, Empty String, or encoded JSON String
        if not attempt.response_data:
            attempt.response_data = {}
        elif isinstance(attempt.response_data, str):
            try:
                attempt.response_data = json.loads(attempt.response_data)
            except:
                attempt.response_data = {}
        
        # Ensure it is definitely a dict now
        if not isinstance(attempt.response_data, dict):
            attempt.response_data = {}

        # 3. Save Metadata (Warnings)
        if 'metadata' not in attempt.response_data:
            attempt.response_data['metadata'] = {}
        
        # Get existing warnings safely
        metadata = attempt.response_data['metadata']
        current_stored = metadata.get('warnings', 0)
        metadata['warnings'] = max(current_stored, warnings)
        
        attempt.response_data['metadata'] = metadata # Re-assign to ensure save

        # 4. Save Answers
        if new_answers:
            attempt.response_data[str(current_section.id)] = new_answers
        
        attempt.save() 
        
        # 5. Logic: Next Section or Finish?
        next_section = None
        if not force_end_exam:
            next_section = ExamSection.objects.filter(
                exam=attempt.exam, 
                order__gt=current_section.order
            ).order_by('order').first()

        if next_section:
            attempt.current_section = next_section
            attempt.section_start_time = timezone.now()
            attempt.save()
            
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
            attempt.current_section = None 
            attempt.save()
            
            # Ensure this function exists and works!
            if 'calculate_final_score' in globals():
                calculate_final_score(attempt)
            
            redirect_url = f'/assessments/result/{attempt.id}/'
            
            if request.method == "POST":
                return JsonResponse({'status': 'finished', 'redirect_url': redirect_url})
            else:
                return redirect('attempt_detail', attempt_id=attempt.id)

    except Exception as e:
        # LOG THE ERROR so you can see it in the terminal
        print(f"CRITICAL ERROR in submit_section: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return JSON error to frontend
        return JsonResponse({
            'status': 'error',
            'message': f'Server Error: {str(e)}'
        }, status=500)

def calculate_final_score(attempt):
    total_obtained = 0
    
    if not attempt.response_data:
        attempt.score = 0
        attempt.passed = False
        attempt.save()
        return

    # 1. Extract Answers (Ignoring Metadata)
    flat_answers = {}
    for sec_id, sec_data in attempt.response_data.items():
        # CRITICAL FIX: Skip the metadata/warnings block
        if sec_id == 'metadata':
            continue
            
        if isinstance(sec_data, dict):
            flat_answers.update(sec_data)

    # 2. Score Calculation
    # We iterate through the ACTUAL questions in the exam to find their answers.
    # This is safer than iterating the JSON keys directly.
    questions = ExamQuestion.objects.filter(section__exam=attempt.exam)
    
    for q in questions:
        # Get user answer safely (as string)
        user_ans = flat_answers.get(str(q.id))
        
        if not user_ans:
            continue

        # Logic for checking answers
        is_correct = False
        
        if q.q_type == 'MCQ_SINGLE':
            if str(user_ans) == str(q.correct_options):
                is_correct = True
                
        elif q.q_type == 'MCQ_MULTI':
            # Handle list or comma-separated string
            if isinstance(user_ans, list):
                u_opts = set(map(str, user_ans))
            else:
                u_opts = set(map(str, str(user_ans).split(',')))
                
            c_opts = set(map(str, str(q.correct_options).split(',')))
            
            if u_opts == c_opts:
                is_correct = True

        elif q.q_type == 'CODE':
            # Coding questions usually require manual review or test case results
            # For now, we assume if they passed test cases in frontend, they get marks.
            # OR you rely on the 'passed_cases' if you stored that.
            # If you want to auto-give marks for code submission:
            if isinstance(user_ans, dict) and user_ans.get('code'):
                # Simple logic: if code exists, give marks (or implement complex checking)
                # Ideally, you stored 'passed' boolean in previous step.
                is_correct = True 

        if is_correct:
            total_obtained += q.marks

    # 3. Save Final Score
    attempt.score = total_obtained
    
    # Calculate Pass/Fail (e.g., 40% threshold)
    total_marks = attempt.exam.total_marks
    if total_marks > 0:
        percentage = (total_obtained / total_marks) * 100
        attempt.passed = percentage >= 40  # Change 40 to your pass mark
    else:
        attempt.passed = True

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
    questions = ExamQuestion.objects.filter(section__exam=attempt.exam).order_by('section__order', 'id')
    
    # --- 1. Parse Response Data & Extract Warnings ---
    flat_answers = {}
    warnings = 0
    
    if attempt.response_data:
        # Check for Metadata (Warnings)
        if 'metadata' in attempt.response_data:
            warnings = attempt.response_data['metadata'].get('warnings', 0)
        
        # Flatten answers (IMPORTANT: Skip 'metadata' key)
        for sec_id, sec_data in attempt.response_data.items():
            if sec_id != 'metadata' and isinstance(sec_data, dict):
                flat_answers.update(sec_data)

    # Check for Malpractice (Threshold > 2)
    is_malpractice = warnings > 2

    # --- 2. Build Report ---
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
                # Sort both lists to compare sets correctly
                if set(map(str, c_opts)) == set(map(str, u_opts)): is_correct = True
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
            'section_name': q.section.name 
        })

    return render(request, 'assessments/attempt_detail.html', {
        'attempt': attempt, 
        'report': report,
        'warnings': warnings,           # <-- Added Context
        'is_malpractice': is_malpractice # <-- Added Context
    })
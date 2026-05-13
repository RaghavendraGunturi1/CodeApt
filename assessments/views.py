import django_rq
from core.models import ExecutionJob
from core.services.rq_jobs import execute_submission_job
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import F
from django.db import transaction
from django.core.cache import cache
import json
import requests 
from concurrent.futures import ThreadPoolExecutor
import threading
from core.services.execution_service import execution_service, ExecutionResult
from .models import (
    Exam,
    ExamSection,
    ExamQuestion,
    StudentExamAttempt,
    ExamAttemptCounter,
    Topic,
    ExamTestCase,
    PublicExamLink
)


# Centralized code execution for assessments

# Hybrid execution: playground sync, submissions async

# Centralized/hardened async job enqueue logic
def enqueue_execution_job(code, lang, stdin, user=None, submission_ref=None, queue='practice'):
    import uuid
    job_id = str(uuid.uuid4())
    # Idempotency: prevent duplicate jobs for same submission_ref if needed
    if submission_ref:
        existing = ExecutionJob.objects.filter(submission_ref=submission_ref, status__in=['queued', 'processing', 'completed']).first()
        if existing:
            return existing.job_id
    job = ExecutionJob.objects.create(
        job_id=job_id,
        user=user if user and user.is_authenticated else None,
        submission_ref=submission_ref,
        queue=queue,
        status='queued',
    )
    q = django_rq.get_queue(queue)
    q.enqueue(execute_submission_job, job_id, code, lang, stdin, user_id=(user.id if user else None), submission_ref=submission_ref, queue=queue)
    return job_id

def run_code_piston(code, lang, stdin, mode='sync', user=None, submission_ref=None, queue='practice'):
    if mode == 'sync':
        result = execution_service.execute_code(code, lang, stdin)
        if result.success:
            return result.stdout.strip()
        elif result.status == 'timeout':
            return "Error: Execution timed out."
        elif result.status == 'compile_error':
            return f"Error: Compilation failed. {result.compile_output.strip()}"
        elif result.status == 'memory_limit':
            return "Error: Memory limit exceeded."
        elif result.status == 'runtime_error':
            return f"Error: Runtime error. {result.stderr.strip()}"
        elif result.status == 'internal_error':
            return f"Error: Internal error. {result.internal_error or result.reason}"
        else:
            return f"Error: Unknown execution error."
    else:
        return enqueue_execution_job(code, lang, stdin, user=user, submission_ref=submission_ref, queue=queue)
from django.views.decorators.csrf import csrf_exempt
# --- API: Poll async execution job status/result ---

from django.contrib.auth.decorators import login_required

# Hardened polling endpoint: authentication, job ownership, safe errors
@csrf_exempt
@login_required
def poll_execution_job(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            job_id = data.get('job_id')
            job = ExecutionJob.objects.get(job_id=job_id)
            # Only allow polling for own jobs
            if job.user and job.user != request.user:
                return JsonResponse({'error': 'Forbidden'}, status=403)
            return JsonResponse({
                'status': job.status,
                'result': job.result,
                'error': job.error,
            })
        except ExecutionJob.DoesNotExist:
            return JsonResponse({'status': 'not_found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def start_exam(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    try:
        exam = topic.exam
    except Exam.DoesNotExist:
        return render(request, 'error.html', {'message': 'No exam found for this topic.'})

    # ✅ CHECK ATTEMPT LIMIT
    attempt_count = exam.get_user_attempt_count(request.user)
    if attempt_count >= exam.max_attempts:
        return render(request, 'error.html', {
            'message': 'Maximum attempts for this exam are exceeded. Contact support for queries.',
            'title': 'Exam Attempts Exceeded'
        })

    attempt = (StudentExamAttempt.objects
               .filter(user=request.user, exam=exam, completed_at__isnull=True)
               .order_by('-id')
               .first())
    created = False
    if not attempt:
        attempt = StudentExamAttempt.objects.create(user=request.user, exam=exam)
        created = True

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

    sections = list(exam.sections.order_by('order').prefetch_related('questions'))
    current_section_index = next((idx for idx, sec in enumerate(sections, start=1) if sec.id == attempt.current_section_id), 1)

    context = {
        'exam': exam,
        'section': attempt.current_section,
        'questions': attempt.current_section.questions.all(),
        'attempt': attempt,
        'time_left': int(time_left),
        'total_sections': len(sections),
        'current_section_index': current_section_index,
        'is_last_section': not next_section_exists,  # <--- PASS THIS TO TEMPLATE
    }
    return render(request, 'assessments/take_section_exam.html', context)


def _section_payload_cache_key(section_id):
    return f"assessment_section_payload:{section_id}"


def _build_section_payload(section):
    questions_data = []
    questions = section.questions.all()
    for q in questions:
        q_data = {
            'id': q.id,
            'type': q.q_type,
            'text': q.text or '',
            'image_url': q.image.url if q.image else None,
            'marks': q.marks,
            'starter_code': q.starter_code or '',
        }
        if q.q_type in ['MCQ_SINGLE', 'MCQ_MULTI']:
            q_data['options'] = {
                '1': q.option_1,
                '2': q.option_2,
                '3': q.option_3,
                '4': q.option_4,
            }
        questions_data.append(q_data)
    return questions_data


def _get_cached_section_questions(section):
    key = _section_payload_cache_key(section.id)
    payload = cache.get(key)
    if payload is None:
        payload = _build_section_payload(section)
        cache.set(key, payload, 300)
    return payload



# All grading is now handled by Redis queue workers. No background threads.


# In assessments/views.py


def submit_section(request, attempt_id):
    try:
        attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

        # ===============================
        # 1️⃣ AUTH VALIDATION
        # ===============================

        # Logged-in attempt
        if attempt.user:
            if not request.user.is_authenticated or attempt.user != request.user:
                return JsonResponse({'status': 'error'}, status=403)

        # Public attempt
        else:
            session_attempt = request.session.get("public_attempt_id")
            if session_attempt != attempt.id:
                return JsonResponse({'status': 'error'}, status=403)

        current_section = attempt.current_section

        # If already completed → show result
        if attempt.completed_at:
            return redirect('attempt_detail', attempt_id=attempt.id)

        if not current_section:
            return JsonResponse({'status': 'error', 'message': 'No active section'}, status=400)

        # ===============================
        # 2️⃣ PARSE REQUEST DATA
        # ===============================

        new_answers = {}
        warnings = 0
        force_end_exam = False

        if request.method == "POST":
            try:
                data = json.loads(request.body)
                new_answers = data.get('answers', {})
                warnings = int(data.get('warnings', 0))
                force_end_exam = data.get('force_end', False)
            except (json.JSONDecodeError, TypeError):
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

        # ===============================
        # 3️⃣ SAFE JSON FIELD HANDLING
        # ===============================

        if not attempt.response_data:
            attempt.response_data = {}
        elif isinstance(attempt.response_data, str):
            try:
                attempt.response_data = json.loads(attempt.response_data)
            except:
                attempt.response_data = {}

        if not isinstance(attempt.response_data, dict):
            attempt.response_data = {}

        # ===============================
        # 4️⃣ STORE WARNINGS
        # ===============================

        metadata = attempt.response_data.get('metadata', {})
        current_stored = metadata.get('warnings', 0)
        metadata['warnings'] = max(current_stored, warnings)
        attempt.response_data['metadata'] = metadata

        # ===============================
        # 5️⃣ SAVE ANSWERS
        # ===============================

        if new_answers:
            attempt.response_data[str(current_section.id)] = new_answers

        attempt.save()

        # ===============================
        # 6️⃣ NEXT SECTION OR FINISH
        # ===============================

        next_section = None
        if not force_end_exam:
            next_section = ExamSection.objects.filter(
                exam=attempt.exam,
                order__gt=current_section.order
            ).order_by('order').first()

        # -------------------------------
        # ➜ GO TO NEXT SECTION
        # -------------------------------
        if next_section:
            attempt.current_section = next_section
            attempt.section_start_time = timezone.now()
            attempt.save()

            # 🔥 FIX: Separate redirect for public vs logged-in
            if attempt.user:
                redirect_url = f'/assessments/start/{attempt.exam.topic.id}/'
            else:
                redirect_url = f'/assessments/public-start/{attempt.id}/'

            return JsonResponse({
                'status': 'next_section',
                'redirect_url': redirect_url
            })

        # -------------------------------
        # ➜ FINISH EXAM
        # -------------------------------
        else:
            attempt.completed_at = timezone.now()
            attempt.current_section = None
            attempt.grading_status = 'PROCESSING'
            attempt.grading_error = ''
            attempt.save()

            # Queue grading job for this attempt (idempotent)
            from core.services.rq_jobs import enqueue_grading_job
            transaction.on_commit(lambda: enqueue_grading_job(attempt.id))

            # Increment restriction counter only when a logged-in user's attempt is completed.
            if attempt.user:
                counter, _ = ExamAttemptCounter.objects.get_or_create(
                    user=attempt.user,
                    exam=attempt.exam,
                    defaults={'attempt_count': 0},
                )
                ExamAttemptCounter.objects.filter(pk=counter.pk).update(attempt_count=F('attempt_count') + 1)

            return JsonResponse({
                'status': 'finished',
                'redirect_url': f'/assessments/result/{attempt.id}/'
            })

    except Exception as e:
        print(f"CRITICAL ERROR in submit_section: {str(e)}")
        import traceback
        traceback.print_exc()

        return JsonResponse({
            'status': 'error',
            'message': f'Server Error: {str(e)}'
        }, status=500)

    
# (No longer needed, all execution is centralized)
def calculate_final_score(attempt):
    total_obtained = 0
    
    # 0. Safety Check: If no data, fail immediately
    if not attempt.response_data:
        attempt.score = 0
        attempt.passed = False
        attempt.save()
        return

    # 1. Extract Answers (CRITICAL FIX: Ignore Metadata)
    flat_answers = {}
    for sec_id, sec_data in attempt.response_data.items():
        # Skip the metadata/warnings block to prevent "Field 'id' expected a number" error
        if sec_id == 'metadata':
            continue
            
        if isinstance(sec_data, dict):
            flat_answers.update(sec_data)

    # 2. Score Calculation
    # We iterate through ACTUAL questions in database to find their answers.
    questions = ExamQuestion.objects.filter(section__exam=attempt.exam)
    
    for q in questions:
        user_ans = flat_answers.get(str(q.id))
        
        # If user didn't answer this question, skip grading
        if not user_ans:
            continue

        is_correct = False
        
        # --- A. MCQ SINGLE ---
        if q.q_type == 'MCQ_SINGLE':
            if str(user_ans) == str(q.correct_options):
                is_correct = True
                
        # --- B. MCQ MULTI ---
        elif q.q_type == 'MCQ_MULTI':
            if isinstance(user_ans, list):
                u_opts = set(map(str, user_ans))
            else:
                u_opts = set(map(str, str(user_ans).split(',')))
                
            c_opts = set(map(str, str(q.correct_options).split(',')))
            
            if u_opts == c_opts:
                is_correct = True

        # --- C. CODING CHALLENGE (SECURE PISTON API) ---
        elif q.q_type == 'CODE':
            user_code = ""
            user_lang = "python" # Default fallback
            
            if isinstance(user_ans, dict):
                user_code = user_ans.get('code', "")
                user_lang = user_ans.get('language', "python")
            
            # Only grade if code exists and there are test cases
            test_cases = ExamTestCase.objects.filter(question=q)
            
            if user_code and test_cases.exists():
                passed_cases = 0
                total_cases = test_cases.count()
                
                # ✅ OPTIMIZED: Run test cases in parallel to avoid timeouts
                with ThreadPoolExecutor(max_workers=5) as executor:
                    # Prepare the work (calling execute_code_piston)
                    futures = [
                        executor.submit(run_code_piston, user_code, user_lang, tc.input_data)
                        for tc in test_cases
                    ]
                    
                    # Gather results
                    for i, future in enumerate(futures):
                        try:
                            actual_output = future.result(timeout=15)
                            clean_actual = actual_output.strip()
                            clean_expected = test_cases[i].expected_output.strip()
                            
                            if clean_actual == clean_expected:
                                passed_cases += 1
                        except Exception:
                            continue # Skip failed/timeout individual cases
                
                # Partial marking: Award marks proportionally to test cases passed
                if passed_cases > 0:
                    partial_points = (passed_cases / total_cases) * q.marks
                    total_obtained += partial_points
                    
            # Skip the standard 'is_correct' boolean addition for coding questions
            continue

        # --- D. ADD MARKS ---
        if is_correct:
            total_obtained += q.marks

    # 3. Save Final Score
    attempt.score = total_obtained
    
    # Calculate Pass/Fail (e.g., 40% threshold)
    total_marks = attempt.exam.total_marks
    if total_marks > 0:
        percentage = (total_obtained / total_marks) * 100
        attempt.passed = percentage >= 40 
    else:
        attempt.passed = True

    attempt.save()


def _build_attempt_report(attempt):
    questions = (ExamQuestion.objects
                 .filter(section__exam=attempt.exam)
                 .select_related('section')
                 .order_by('section__order', 'id'))

    flat_answers = {}
    warnings = 0

    if attempt.response_data:
        if 'metadata' in attempt.response_data:
            warnings = attempt.response_data['metadata'].get('warnings', 0)

        for sec_id, sec_data in attempt.response_data.items():
            if sec_id != 'metadata' and isinstance(sec_data, dict):
                flat_answers.update(sec_data)

    is_malpractice = warnings > 2
    report = []

    for q in questions:
        user_ans = flat_answers.get(str(q.id))
        is_correct = False
        correct_display = q.correct_options
        user_display = user_ans

        if q.q_type == 'MCQ_SINGLE':
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            correct_display = options.get(str(q.correct_options), "N/A")
            user_display = options.get(str(user_ans), "Not Attempted")
            if str(user_ans) == str(q.correct_options):
                is_correct = True
        elif q.q_type == 'MCQ_MULTI':
            options = {'1': q.option_1, '2': q.option_2, '3': q.option_3, '4': q.option_4}
            c_opts = str(q.correct_options).split(',')
            correct_display = ", ".join([options.get(o, o) for o in c_opts])
            if user_ans:
                u_opts = user_ans if isinstance(user_ans, list) else [user_ans]
                user_display = ", ".join([options.get(str(o), str(o)) for o in u_opts])
                if set(map(str, c_opts)) == set(map(str, u_opts)):
                    is_correct = True
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

    return report, warnings, is_malpractice

@login_required
def check_code(request, question_id):
    """
    Runs code against visible test cases only.
    Hidden test cases are reserved for final scoring.
    """
    if request.method == "POST":
        data = json.loads(request.body)
        code = data.get('code')
        language = data.get('language', 'python')
        
        question = get_object_or_404(ExamQuestion, id=question_id)
        test_cases = question.test_cases.filter(is_hidden=False)
        

        total_cases = test_cases.count()
        if total_cases == 0:
            return JsonResponse({'status': 'error', 'message': 'No test cases configured.'})

        import logging
        logger = logging.getLogger('ExecutionService')
        job_ids = []
        for case in test_cases:
            job = enqueue_execution_job(
                code, language, case.input_data,
                user=request.user,
                submission_ref=f"checkcode-{question_id}-tc{case.id}-user{request.user.id}",
                queue='practice'
            )
            logger.info(f"[ENQUEUE] Assessment check_code job: job_id={job} user={request.user} question_id={question_id} testcase_id={case.id}")
            job_ids.append({'job_id': job, 'testcase_id': case.id})

        return JsonResponse({
            'status': 'queued',
            'job_ids': job_ids,
            'total_cases': total_cases
        })
        
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def exam_history(request):
    attempts = (StudentExamAttempt.objects
                .filter(user=request.user, completed_at__isnull=False)
                .select_related('exam', 'exam__topic')
                .order_by('-completed_at'))
    return render(request, 'assessments/exam_history.html', {'attempts': attempts})


def attempt_detail(request, attempt_id):
    """Detailed Report Card"""

    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    # ===============================
    # 🔐 ACCESS VALIDATION
    # ===============================

    # Case 1: Logged-in attempt
    if attempt.user:
        if not request.user.is_authenticated or attempt.user != request.user:
            return redirect("dashboard")

    # Case 2: Public attempt
    else:
        session_attempt = request.session.get("public_attempt_id")
        if session_attempt != attempt.id:
            return redirect("dashboard")

    if attempt.grading_status != 'DONE':
        return render(request, 'assessments/attempt_detail.html', {
            'attempt': attempt,
            'report': [],
            'warnings': attempt.response_data.get('metadata', {}).get('warnings', 0) if attempt.response_data else 0,
            'is_malpractice': False,
            'grading_pending': True,
        })

    report, warnings, is_malpractice = _build_attempt_report(attempt)

    return render(request, 'assessments/attempt_detail.html', {
        'attempt': attempt,
        'report': report,
        'warnings': warnings,
        'is_malpractice': is_malpractice,
        'grading_pending': False,
    })


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from .models import ExamQuestion, ExamTestCase
# (No longer needed, all execution is centralized)

@csrf_exempt
def run_question_test_cases(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            q_id = data.get('q_id')
            code = data.get('code')
            lang = data.get('language', 'python')

            # 1. Get Question & Test Cases
            question = ExamQuestion.objects.get(id=q_id)
            test_cases = ExamTestCase.objects.filter(question=question, is_hidden=False)

            if not test_cases.exists():
                return JsonResponse({'error': 'No visible test cases found for this question.'})

            results = []
            all_passed = True

            # 2. Run Each Test Case in Parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_case = {
                    executor.submit(run_code_piston, code, lang, tc.input_data): tc
                    for tc in test_cases
                }
                
                for future in future_to_case:
                    tc = future_to_case[future]
                    try:
                        actual_output = future.result(timeout=15)
                        clean_actual = actual_output.strip()
                        clean_expected = tc.expected_output.strip()
                        
                        passed = (clean_actual == clean_expected)
                        if not passed:
                            all_passed = False

                        results.append({
                            'case_num': len(results) + 1,
                            'input': tc.input_data,
                            'expected': clean_expected,
                            'actual': clean_actual,
                            'passed': passed
                        })
                    except Exception as e:
                        all_passed = False
                        results.append({
                            'case_num': len(results) + 1,
                            'input': tc.input_data,
                            'expected': tc.expected_output.strip(),
                            'actual': f"Error: {str(e)}",
                            'passed': False
                        })

            return JsonResponse({'status': 'success', 'results': results, 'all_passed': all_passed})

        except ExamQuestion.DoesNotExist:
            return JsonResponse({'error': 'Question not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=400)


def public_start_exam(request, attempt_id):
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    exam = attempt.exam

    if not attempt.current_section:
        first_section = exam.sections.order_by('order').first()
        attempt.current_section = first_section
        attempt.section_start_time = timezone.now()
        attempt.save()

    elapsed = (timezone.now() - attempt.section_start_time).total_seconds()
    duration_sec = attempt.current_section.duration_minutes * 60
    time_left = max(0, duration_sec - elapsed)

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
        'is_last_section': not next_section_exists,
    }

    return render(request, 'assessments/take_section_exam.html', context)

def public_exam_entry(request, token):
    link = get_object_or_404(PublicExamLink, access_token=token)

    if not link.is_available():
        return render(request, "assessments/error.html", {
            "message": "Exam is not available."
        })

    if request.method == "POST":
        roll = request.POST.get("roll_number")
        college = request.POST.get("college_name")

        attempt = StudentExamAttempt.objects.create(
            exam=link.exam,
            public_link=link,   # 🔥 IMPORTANT
            roll_number=roll,
            college_name=college
        )

        request.session["public_attempt_id"] = attempt.id

        return redirect("public_start_exam", attempt_id=attempt.id)

    return render(request, "assessments/public_exam_entry.html", {
        "exam": link.exam
    })

import openpyxl
from django.http import HttpResponse

@login_required
def export_exam_results(request, exam_id):
    exam = Exam.objects.get(id=exam_id)

    attempts = (StudentExamAttempt.objects
                .filter(exam=exam, completed_at__isnull=False)
                .select_related('user'))

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Results"

    sheet.append([
        "Roll Number",
        "College",
        "Username",
        "Score",
        "Passed",
        "Completed At"
    ])

    for a in attempts:
        sheet.append([
            a.roll_number or "",
            a.college_name or "",
            a.user.username if a.user else "",
            a.score,
            a.passed,
            a.completed_at.strftime("%Y-%m-%d %H:%M") if a.completed_at else ""
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = f'attachment; filename={exam.topic.name}_results.xlsx'

    workbook.save(response)
    return response


# NEW: Load section data for seamless AJAX transitions
def load_section_data(request, attempt_id):
    """
    AJAX endpoint to fetch next section data without page reload.
    Returns JSON with question data, timer info, and section details.
    """
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)
    
    # Auth checks
    if attempt.user:
        if not request.user.is_authenticated or attempt.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    else:
        session_attempt = request.session.get("public_attempt_id")
        if session_attempt != attempt.id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    section = attempt.current_section
    if not section:
        return JsonResponse({'status': 'error', 'message': 'No active section'}, status=400)
    
    # Calculate time left
    elapsed = (timezone.now() - attempt.section_start_time).total_seconds()
    duration_sec = section.duration_minutes * 60
    time_left = max(0, duration_sec - elapsed)
    
    # Check if this is the last section
    next_section_exists = ExamSection.objects.filter(
        exam=attempt.exam,
        order__gt=section.order
    ).exists()
    
    questions_data = _get_cached_section_questions(section)
    
    return JsonResponse({
        'status': 'success',
        'section': {
            'id': section.id,
            'name': section.name,
            'duration_minutes': section.duration_minutes,
            'order': section.order,
        },
        'exam': {
            'id': attempt.exam.id,
            'topic_name': attempt.exam.topic.name if attempt.exam.topic else 'Unknown',
            'total_sections': attempt.exam.sections.count(),
        },
        'attempt_id': attempt.id,
        'time_left': int(time_left),
        'current_section_index': list(attempt.exam.sections.order_by('order')).index(section) + 1,
        'is_last_section': not next_section_exists,
        'questions': questions_data,
    })


@login_required
def result_status(request, attempt_id):
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    if attempt.user:
        if not request.user.is_authenticated or attempt.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    else:
        session_attempt = request.session.get("public_attempt_id")
        if session_attempt != attempt.id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    return JsonResponse({
        'status': 'success',
        'grading_status': attempt.grading_status,
        'score': attempt.score,
        'passed': attempt.passed,
        'redirect_url': f'/assessments/result/{attempt.id}/' if attempt.grading_status == 'DONE' else None,
        'error': attempt.grading_error,
    })
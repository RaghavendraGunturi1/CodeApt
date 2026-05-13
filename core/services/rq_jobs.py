import django_rq
from core.models import ExecutionJob
import uuid
# Utility to enqueue grading job for an attempt (idempotent)
def enqueue_grading_job(attempt_id):
    submission_ref = f"attempt-{attempt_id}"
    existing = ExecutionJob.objects.filter(submission_ref=submission_ref, status__in=['queued', 'processing', 'completed']).first()
    if existing:
        return existing.job_id
    job_id = str(uuid.uuid4())
    job = ExecutionJob.objects.create(
        job_id=job_id,
        submission_ref=submission_ref,
        queue='assessment',
        status='queued',
    )
    q = django_rq.get_queue('assessment')
    q.enqueue(execute_grading_job_worker, job_id, attempt_id)
    return job_id

# Worker for grading an assessment attempt (atomic, idempotent)
def execute_grading_job_worker(job_id, attempt_id):
    from assessments.models import StudentExamAttempt
    from django.db import transaction
    from django.utils import timezone as djtz
    import logging
    logger = logging.getLogger('rq.worker')
    job = None
    try:
        job = ExecutionJob.objects.get(job_id=job_id)
        if job.status in ('completed', 'failed'):
            logger.warning(f"Grading job {job_id} already finalized. Skipping.")
            return job.result or {'success': False, 'status': 'duplicate', 'reason': 'Already finalized'}
        job.status = 'processing'
        job.started_at = djtz.now()
        job.save(update_fields=['status', 'started_at'])
    except ExecutionJob.DoesNotExist:
        logger.error(f"ExecutionJob not found for grading job_id={job_id}")
        return {'success': False, 'status': 'not_found', 'reason': 'Job not found'}

    try:
        with transaction.atomic():
            attempt = StudentExamAttempt.objects.select_for_update().get(id=attempt_id)
            # Idempotency: skip if already graded
            if attempt.grading_status == 'DONE':
                logger.warning(f"Attempt {attempt_id} already graded. Skipping.")
                job.status = 'completed'
                job.result = {'success': True, 'status': 'already_graded'}
                job.finished_at = djtz.now()
                job.save(update_fields=['status', 'result', 'finished_at'])
                return job.result
            # Timer safety: check if expired
            if attempt.completed_at and attempt.exam and hasattr(attempt, 'section_start_time'):
                elapsed = (attempt.completed_at - attempt.section_start_time).total_seconds() if attempt.section_start_time else 0
                duration_sec = getattr(attempt.current_section, 'duration_minutes', 0) * 60 if attempt.current_section else 0
                if duration_sec and elapsed > duration_sec:
                    logger.warning(f"Attempt {attempt_id} expired. Skipping grading.")
                    attempt.grading_status = 'FAILED'
                    attempt.grading_error = 'Expired'
                    attempt.graded_at = djtz.now()
                    attempt.save(update_fields=['grading_status', 'grading_error', 'graded_at'])
                    job.status = 'failed'
                    job.result = {'success': False, 'status': 'expired', 'reason': 'Attempt expired'}
                    job.finished_at = djtz.now()
                    job.save(update_fields=['status', 'result', 'finished_at'])
                    return job.result
            # Perform grading (atomic)
            from assessments.views import calculate_final_score
            calculate_final_score(attempt)
            attempt.grading_status = 'DONE'
            attempt.grading_error = ''
            attempt.graded_at = djtz.now()
            attempt.save(update_fields=['grading_status', 'grading_error', 'graded_at'])
            job.status = 'completed'
            job.result = {'success': True, 'status': 'graded'}
            job.finished_at = djtz.now()
            job.save(update_fields=['status', 'result', 'finished_at'])
        logger.info(f"Grading job {job_id} for attempt {attempt_id} completed.")
        return job.result
    except Exception as e:
        logger.exception(f"Grading job {job_id} failed: {str(e)}")
        if job:
            job.status = 'failed'
            job.result = {'success': False, 'status': 'internal_error', 'reason': str(e)}
            job.finished_at = djtz.now()
            job.save(update_fields=['status', 'result', 'finished_at'])
        return {'success': False, 'status': 'internal_error', 'reason': str(e)}
import django_rq
from core.services.execution_service import execution_service
from core.models import ExecutionJob
from django.utils import timezone
import logging

logger = logging.getLogger('rq.worker')

def execute_submission_job(job_id, code, language, stdin, user_id=None, submission_ref=None, queue='practice'):
    """
    Hardened RQ worker job for async code execution.
    - Idempotency: Prevents duplicate grading.
    - Timer/locking: Respects assessment timing and accepted locking.
    - Atomic DB updates for grading/leaderboard.
    - Logs all failures and stuck jobs.
    """
    from django.db import transaction
    job = None
    try:
        job = ExecutionJob.objects.get(job_id=job_id)
        if job.status in ('completed', 'failed'):
            logger.warning(f"Job {job_id} already finalized. Skipping duplicate execution.")
            return job.result or {'success': False, 'status': 'duplicate', 'reason': 'Already finalized'}
        job.status = 'processing'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])
    except ExecutionJob.DoesNotExist:
        logger.error(f"ExecutionJob not found for job_id={job_id}")
        return {'success': False, 'status': 'not_found', 'reason': 'Job not found'}

    # --- Idempotency: Check submission/attempt state if possible ---
    # If submission_ref is an attempt or submission ID, check its state
    # (Pseudo-code, adapt to your actual models/logic)
    if submission_ref and submission_ref.startswith('attempt-'):
        from assessments.models import StudentExamAttempt
        attempt_id = submission_ref.replace('attempt-', '')
        try:
            attempt = StudentExamAttempt.objects.get(id=attempt_id)
            # Timer safety: Check if expired
            if attempt.completed_at:
                logger.warning(f"Attempt {attempt_id} already completed. Skipping.")
                job.status = 'completed'
                job.result = {'success': False, 'status': 'duplicate', 'reason': 'Attempt already completed'}
                job.finished_at = timezone.now()
                job.save(update_fields=['status', 'result', 'finished_at'])
                return job.result
            if hasattr(attempt, 'exam') and hasattr(attempt, 'section_start_time'):
                from django.utils import timezone as djtz
                elapsed = (djtz.now() - attempt.section_start_time).total_seconds()
                duration_sec = getattr(attempt.current_section, 'duration_minutes', 0) * 60 if attempt.current_section else 0
                if duration_sec and elapsed > duration_sec:
                    logger.warning(f"Attempt {attempt_id} expired. Skipping grading.")
                    job.status = 'failed'
                    job.result = {'success': False, 'status': 'expired', 'reason': 'Attempt expired'}
                    job.finished_at = timezone.now()
                    job.save(update_fields=['status', 'result', 'finished_at'])
                    return job.result
        except StudentExamAttempt.DoesNotExist:
            logger.error(f"Attempt {attempt_id} not found for job {job_id}")
            job.status = 'failed'
            job.result = {'success': False, 'status': 'not_found', 'reason': 'Attempt not found'}
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'result', 'finished_at'])
            return job.result

    try:
        # --- Atomic grading/leaderboard update ---
        with transaction.atomic():
            result = execution_service.execute_code(code, language, stdin)
            # (Pseudo-code: update submission/attempt/leaderboard here atomically)
            # e.g., if submission_ref is attempt, update attempt score/accepted only if not already accepted
            # ...
            job.result = result.to_dict()
            job.status = 'completed' if result.success else 'failed'
            job.error = result.internal_error or result.reason or ''
            job.finished_at = timezone.now()
            job.save(update_fields=['result', 'status', 'error', 'finished_at'])
        logger.info(f"ExecutionJob {job_id} completed. Status: {job.status if job else 'unknown'}")
        return result.to_dict()
    except Exception as e:
        logger.exception(f"ExecutionJob {job_id} failed: {str(e)}")
        if job:
            job.status = 'failed'
            job.error = str(e)
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'error', 'finished_at'])
        return {'success': False, 'status': 'internal_error', 'reason': str(e)}

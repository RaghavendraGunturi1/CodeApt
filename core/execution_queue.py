def enqueue_grading_job(attempt_id, queue_name=None):
    """
    Enqueue a grading job for an assessment attempt.
    """
    from core.models import ExecutionJob
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # Use assessment queue by default
    if not queue_name:
        queue_name = ASSESSMENT_QUEUE
    # Create a job record for tracking (optional, or reuse if needed)
    job = ExecutionJob.objects.create(
        job_type='assessment',
        related_id=str(attempt_id),
        status='queued',
        queue_name=queue_name,
    )
    queue = django_rq.get_queue(queue_name)
    rq_job = queue.enqueue(
        "core.execution_queue.execute_grading_job_worker",
        attempt_id,
        job.id,
        retry=settings.RQ_RETRY_COUNT,
        job_timeout=settings.RQ_QUEUES[queue_name]["DEFAULT_TIMEOUT"],
    )
    job.log = f"Enqueued grading RQ job: {rq_job.id}"
    job.save(update_fields=["log"])
    logger.info(f"Enqueued grading job for attempt {attempt_id} to {queue_name} (RQ id: {rq_job.id})")
    return job

def execute_grading_job_worker(attempt_id, job_id=None):
    """
    Worker function: grades an assessment attempt (idempotent, atomic, safe).
    Updates grading status and ExecutionJob if job_id is provided.
    """
    import django
    django.setup()
    from assessments.models import StudentExamAttempt
    from core.models import ExecutionJob
    from django.db import transaction
    from django.utils import timezone
    import logging
    logger = logging.getLogger("core.execution_queue")
    try:
        with transaction.atomic():
            attempt = StudentExamAttempt.objects.select_for_update().get(id=attempt_id)
            # Idempotency: Only grade if not already graded
            if attempt.grading_status == 'DONE':
                logger.info(f"Attempt {attempt_id} already graded. Skipping.")
                if job_id:
                    job = ExecutionJob.objects.get(id=job_id)
                    job.mark_completed({'info': 'Already graded'})
                return
            # Timer enforcement: do not grade expired attempts
            if attempt.completed_at and attempt.exam:
                # Optionally check for exam/section expiry here
                pass
            from assessments.views import calculate_final_score
            calculate_final_score(attempt)
            attempt.grading_status = 'DONE'
            attempt.grading_error = ''
            attempt.graded_at = timezone.now()
            attempt.save(update_fields=['grading_status', 'grading_error', 'graded_at', 'score', 'passed'])
            if job_id:
                job = ExecutionJob.objects.get(id=job_id)
                job.mark_completed({'info': 'Grading complete'})
            logger.info(f"Grading complete for attempt {attempt_id}")
    except Exception as exc:
        # Log Redis/worker/DB failures for observability
        logger.exception(f"Grading failed for attempt {attempt_id}: {exc}")
        if job_id:
            try:
                job = ExecutionJob.objects.get(id=job_id)
                job.mark_failed(str(exc))
            except Exception as job_exc:
                logger.error(f"Failed to update ExecutionJob status for job {job_id}: {job_exc}")
        # Mark grading as failed for the attempt
        try:
            StudentExamAttempt.objects.filter(id=attempt_id).update(
                grading_status='FAILED',
                grading_error=str(exc),
                graded_at=timezone.now(),
            )
        except Exception as update_exc:
            logger.error(f"Failed to update grading status for attempt {attempt_id}: {update_exc}")
        # Optionally: implement stuck job detection, alerting, or retry exhaustion handling here
import django_rq
from core.models import ExecutionJob
from django.conf import settings
from core.services.execution_service import execution_service
import logging

logger = logging.getLogger("core.execution_queue")

# --- Queue Names ---
PRACTICE_QUEUE = getattr(settings, "RQ_PRACTICE_QUEUE", "practice")
ASSESSMENT_QUEUE = getattr(settings, "RQ_ASSESSMENT_QUEUE", "assessment")

# --- Job Enqueue Utility ---
def enqueue_execution_job(job_type, user, code, language, input_data, related_id=None, queue_name=None):
    """
    Enqueue a code execution job and create ExecutionJob record.
    job_type: 'assessment' or 'practice'
    related_id: e.g. attempt id or submission id
    queue_name: override queue (default: by job_type)
    Returns: ExecutionJob instance
    """
    if not queue_name:
        queue_name = ASSESSMENT_QUEUE if job_type == 'assessment' else PRACTICE_QUEUE
    job = ExecutionJob.objects.create(
        user=user,
        job_type=job_type,
        related_id=related_id,
        status='queued',
        queue_name=queue_name,
    )
    queue = django_rq.get_queue(queue_name)
    rq_job = queue.enqueue(
        "core.execution_queue.execute_code_job_worker",
        job.id,
        code,
        language,
        input_data,
        retry=settings.RQ_RETRY_COUNT,
        job_timeout=settings.RQ_QUEUES[queue_name]["DEFAULT_TIMEOUT"],
    )
    job.log = f"Enqueued RQ job: {rq_job.id}"
    job.save(update_fields=["log"])
    logger.info(f"Enqueued job {job.id} to {queue_name} (RQ id: {rq_job.id})")
    return job

def execute_code_job_worker(job_id, code, language, input_data):
    """
    Worker function: runs in RQ worker process.
    Updates ExecutionJob status/result.
    """
    import django
    django.setup()
    from core.models import ExecutionJob
    import time
    job = ExecutionJob.objects.get(id=job_id)
    job.mark_processing()
    try:
        result = execution_service.execute_code(code, language, input_data)
        job.mark_completed(result.to_dict())
        return result.to_dict()
    except Exception as e:
        job.mark_failed(str(e))
        raise

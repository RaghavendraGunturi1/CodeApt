# core/utils.py

# Centralized execution service import for all code execution
from core.services.execution_service import execution_service, ExecutionResult


import logging
import django_rq
from core.models import ExecutionJob
import uuid
from core.services.rq_jobs import execute_submission_job

def execute_code_piston(code, language, input_data="", user=None, submission_ref=None, queue="playground", async_mode=True):
    """
    Async wrapper for playground and exam code execution. Enqueues job and returns job_id for polling.
    If async_mode is False, falls back to legacy sync execution (for rare direct calls).
    """
    logger = logging.getLogger("ExecutionService")
    if async_mode:
        job_id = str(uuid.uuid4())
        job = ExecutionJob.objects.create(
            job_id=job_id,
            user=user if user and hasattr(user, 'is_authenticated') and user.is_authenticated else None,
            submission_ref=submission_ref,
            queue=queue,
            status='queued',
        )
        q = django_rq.get_queue(queue)
        q.enqueue(execute_submission_job, job_id, code, language, input_data, user_id=(user.id if user else None), submission_ref=submission_ref, queue=queue)
        logger.info(f"[ENQUEUE] Playground/Exam job enqueued: job_id={job_id} queue={queue} user={user}")
        return {'job_id': job_id, 'status': 'queued'}
    # Legacy sync fallback (should not be used in normal flows)
    result = execution_service.execute_code(code, language, input_data)
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

from django.http import JsonResponse
from core.models import ExecutionJob
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

import threading
import time

# Simple in-memory rate limiter (process-local)
_ai_report_lock = threading.Lock()
_ai_report_last_time = 0
_AI_REPORT_RATE_LIMIT_SECONDS = 20
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from django.contrib.auth.decorators import login_required

@csrf_exempt
@login_required
@require_POST
def generate_ai_report(request):
    from .models import EssayAttempt
    global _ai_report_last_time
    try:
        # Rate limit: 1 request per 20 seconds (process-local, auto-queue)
        while True:
            with _ai_report_lock:
                now = time.time()
                wait_time = _AI_REPORT_RATE_LIMIT_SECONDS - (now - _ai_report_last_time)
                if wait_time <= 0:
                    _ai_report_last_time = now
                    break
            # Wait outside the lock to avoid blocking others
            time.sleep(max(0.5, min(wait_time, 2)))
        data = json.loads(request.body.decode('utf-8'))
        essay_content = data.get('essay')
        attempt_id = data.get('attempt_id')
        if not essay_content or not isinstance(essay_content, str):
            return JsonResponse({'success': False, 'error': 'No essay content provided.'}, status=400)
        if not attempt_id:
            return JsonResponse({'success': False, 'error': 'No attempt ID provided.'}, status=400)
        attempt = EssayAttempt.objects.filter(id=attempt_id, user=request.user).first()
        if not attempt:
            return JsonResponse({'success': False, 'error': 'Essay attempt not found.'}, status=404)
        if attempt.ai_report:
            return JsonResponse({'success': True, 'response': attempt.ai_report, 'already_generated': True})
        # Enforce context limit (32k tokens, ~24,000 words for safety)
        MAX_WORDS = 24000
        essay_words = essay_content.split()
        if len(essay_words) > MAX_WORDS:
            return JsonResponse({
                'success': False,
                'error': f'Essay is too long for AI analysis. Please reduce to under {MAX_WORDS} words.',
                'context_limit': MAX_WORDS
            }, status=400)
        safe_essay_content = ' '.join(essay_words[:MAX_WORDS])
        prompt = (
            "Analyze the following essay in detail. Provide a comprehensive report including strengths, "
            "weaknesses, writing style, coherence, vocabulary, grammar, and suggestions for improvement.\n\nEssay:\n" + safe_essay_content
        )
        print(f"[AI REPORT DEBUG] Prompt length: {len(prompt)}")
        print(f"[AI REPORT DEBUG] Prompt preview: {prompt[:200]}")
        api_response = requests.post(
            "https://apifreellm.com/api/v1/chat",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": "Bearer apf_t1mih7ihealft5o963v03rjb"
            },
            json={"message": prompt},
            timeout=300  # 5 minutes
        )
        if api_response.status_code == 200:
            result = api_response.json()
            report = result.get('response') or result.get('result') or result.get('message')
            if report:
                attempt.ai_report = report
                attempt.save(update_fields=['ai_report', 'updated_at'])
            return JsonResponse({'success': True, 'response': report})
        else:
            return JsonResponse({'success': False, 'error': 'AI service error', 'status_code': api_response.status_code}, status=502)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

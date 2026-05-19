from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import EssayAttempt

@login_required
def essay_attempt_history(request):
    attempts = EssayAttempt.objects.filter(user=request.user).select_related('essay_topic').order_by('-submitted_at', '-created_at')
    return render(request, 'essays/essay_attempt_history.html', {'attempts': attempts})

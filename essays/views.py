from django.db.models import F
from .models import EssayDraft, EssayAnalytics
from .utils import detect_suspicious_activity
import datetime
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
class EssayAnalyticsAjaxView(LoginRequiredMixin, View):
    def post(self, request, id):
        import json
        attempt = get_object_or_404(EssayAttempt, id=id)
        if attempt.user != request.user:
            return JsonResponse({'success': False, 'error': 'Not allowed.'}, status=403)
        data = json.loads(request.body.decode('utf-8'))
        event_type = data.get('event_type')
        inactivity_seconds = int(data.get('inactivity_seconds', 0))
        pause_seconds = int(data.get('pause_seconds', 0))
        now = timezone.now()
        analytics, _ = EssayAnalytics.objects.get_or_create(essay_attempt=attempt)
        # Rate limit: update at most every 5 seconds
        if analytics.last_activity_at and (now - analytics.last_activity_at).total_seconds() < 5:
            return JsonResponse({'success': True, 'rate_limited': True})
        update_fields = []
        if event_type == 'typing':
            analytics.typing_events = F('typing_events') + 1
            update_fields.append('typing_events')
        elif event_type == 'paste':
            analytics.paste_events = F('paste_events') + 1
            update_fields.append('paste_events')
        elif event_type == 'copy':
            analytics.copy_events = F('copy_events') + 1
            update_fields.append('copy_events')
        elif event_type == 'delete':
            analytics.delete_events = F('delete_events') + 1
            update_fields.append('delete_events')
        elif event_type == 'focus_loss':
            analytics.focus_loss_count = F('focus_loss_count') + 1
            update_fields.append('focus_loss_count')
        if inactivity_seconds:
            analytics.inactivity_seconds = F('inactivity_seconds') + inactivity_seconds
            update_fields.append('inactivity_seconds')
        if pause_seconds and pause_seconds > analytics.longest_pause_seconds:
            analytics.longest_pause_seconds = pause_seconds
            update_fields.append('longest_pause_seconds')
        analytics.last_activity_at = now
        update_fields.append('last_activity_at')
        # Save aggregated fields
        analytics.save(update_fields=update_fields)
        # Suspicious detection
        analytics.refresh_from_db()
        result = detect_suspicious_activity(analytics, attempt)
        analytics.suspicious_activity = result['suspicious']
        analytics.risk_score = result['risk_score']
        analytics.save(update_fields=['suspicious_activity', 'risk_score'])
        return JsonResponse({'success': True, 'suspicious': analytics.suspicious_activity, 'risk_score': analytics.risk_score, 'reasons': result['reasons']})
def placeholder_view(request):
    return render(request, 'essays/placeholder.html')

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseNotAllowed
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.utils.decorators import method_decorator
from .models import EssayTopic, EssayAttempt
from .utils import calculate_word_count, calculate_character_count, calculate_paragraph_count, validate_essay_content
from .exceptions import EssayPermissionDenied, EssaySubmissionError, EssayValidationError, EssayAutosaveError

class EssayAttemptListView(LoginRequiredMixin, ListView):
    template_name = 'essays/essay_list.html'
    context_object_name = 'topics'

    def get_queryset(self):
        return EssayTopic.objects.filter(is_active=True).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # Get latest attempt per topic for this user
        attempts = (EssayAttempt.objects.filter(user=user)
                    .order_by('essay_topic', '-attempt_number'))
        latest_attempts_map = {}
        for attempt in attempts:
            if attempt.essay_topic_id not in latest_attempts_map:
                latest_attempts_map[attempt.essay_topic_id] = attempt
        context['latest_attempts_map'] = latest_attempts_map
        return context

class EssayAttemptStartView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user
        topic_id = request.POST.get('topic_id')
        topic = get_object_or_404(EssayTopic, id=topic_id, is_active=True)
        with transaction.atomic():
            # Find latest attempt number for this user/topic
            last_attempt = (EssayAttempt.objects.filter(user=user, essay_topic=topic)
                            .order_by('-attempt_number').first())
            attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1
            attempt = EssayAttempt.objects.create(
                user=user,
                essay_topic=topic,
                attempt_number=attempt_number,
                status=EssayAttempt.StatusChoices.IN_PROGRESS,
                time_limit_seconds=topic.time_limit_minutes * 60,
                ip_address=self._get_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        return redirect('essays:essay_editor', attempt.id)

    def _get_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class EssayEditorView(LoginRequiredMixin, View):
    def get(self, request, id):
        attempt = get_object_or_404(EssayAttempt, id=id)
        if attempt.user != request.user:
            return HttpResponseForbidden('Not allowed.')
        topic = attempt.essay_topic
        can_edit = attempt.can_edit()
        time_remaining = attempt.get_time_remaining()
        validation = validate_essay_content(attempt.content, topic)
        recovered_draft = False
        # Draft recovery: if attempt content is empty, restore latest draft
        if not attempt.content:
            from .models import EssayDraft
            latest_draft = EssayDraft.objects.filter(essay_attempt=attempt).order_by('-saved_at').first()
            if latest_draft:
                attempt.content = latest_draft.content
                attempt.word_count = latest_draft.word_count
                recovered_draft = True
        # Auto-submit if timer expired
        if attempt.is_timed and attempt.is_time_expired() and attempt.status == EssayAttempt.StatusChoices.IN_PROGRESS:
            attempt.status = EssayAttempt.StatusChoices.SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['status', 'submitted_at', 'updated_at'])
            can_edit = False
        return render(request, 'essays/essay_editor.html', {
            'attempt': attempt,
            'topic': topic,
            'time_remaining': time_remaining,
            'validation': validation,
            'can_edit': can_edit,
            'recovered_draft': recovered_draft,
            'max_attempts': getattr(topic, 'max_attempts', 3),
        })

@method_decorator(csrf_protect, name='dispatch')

class SaveDraftAjaxView(LoginRequiredMixin, View):
    def post(self, request, id):
        import json
        try:
            attempt = get_object_or_404(EssayAttempt, id=id)
            if attempt.user != request.user:
                raise EssayPermissionDenied('Not allowed.')
            if not attempt.can_edit():
                raise EssayPermissionDenied('Attempt not editable.')
            data = json.loads(request.body.decode('utf-8'))
            content = data.get('content', '')
            now = timezone.now()
            # Rate limit: 10s between saves
            if hasattr(attempt, '_last_save_time'):
                if (now - attempt._last_save_time).total_seconds() < 10:
                    raise EssayAutosaveError('Too many saves. Please wait.')
            # Do not save if unchanged
            if content == attempt.content:
                return JsonResponse({
                    'success': True,
                    'word_count': attempt.word_count,
                    'character_count': attempt.character_count,
                    'paragraph_count': attempt.paragraph_count,
                    'saved_at': attempt.updated_at,
                    'validation': validate_essay_content(attempt.content, attempt.essay_topic)
                })
            # Update fields
            attempt.content = content
            attempt.word_count = calculate_word_count(content)
            attempt.character_count = calculate_character_count(content)
            attempt.paragraph_count = calculate_paragraph_count(content)
            attempt.updated_at = now
            attempt.save(update_fields=['content', 'word_count', 'character_count', 'paragraph_count', 'updated_at'])
            attempt._last_save_time = now
            # --- Draft snapshot logic ---
            # Only create draft if content changed significantly, or 60s passed, or first draft
            drafts = EssayDraft.objects.filter(essay_attempt=attempt).order_by('-saved_at')
            create_draft = False
            if not drafts.exists():
                create_draft = True
            else:
                last_draft = drafts.first()
                time_since_last = (now - last_draft.saved_at).total_seconds()
                content_changed = abs(len(content) - len(last_draft.content)) > 30 or content != last_draft.content
                if content_changed or time_since_last > 60:
                    create_draft = True
            if create_draft:
                EssayDraft.objects.create(
                    essay_attempt=attempt,
                    content=content,
                    word_count=attempt.word_count
                )
                # Keep only latest 10 drafts
                ids_to_keep = EssayDraft.objects.filter(essay_attempt=attempt).order_by('-saved_at').values_list('id', flat=True)[:10]
                EssayDraft.objects.filter(essay_attempt=attempt).exclude(id__in=ids_to_keep).delete()
            return JsonResponse({
                'success': True,
                'word_count': attempt.word_count,
                'character_count': attempt.character_count,
                'paragraph_count': attempt.paragraph_count,
                'saved_at': attempt.updated_at,
                'validation': validate_essay_content(attempt.content, attempt.essay_topic)
            })
        except EssayPermissionDenied as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)
        except EssayAutosaveError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=429)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


# --- Essay Results View ---
from .services.scoring_service import EssayScorer

class EssayResultsView(LoginRequiredMixin, View):
    def get(self, request, id):
        attempt = get_object_or_404(EssayAttempt, id=id)
        if attempt.user != request.user and not request.user.is_staff:
            return HttpResponseForbidden()
        if request.GET.get('violation') == '1':
            return render(request, 'essays/essay_violation.html', {'attempt': attempt})
        if attempt.final_score is None or attempt.grading_status != 'completed':
            # Score if not already scored (should not happen in prod)
            EssayScorer().score_essay(attempt)
        # Prepare strengths/weaknesses
        strengths = []
        weaknesses = []
        categories = [
            ('Grammar', attempt.grammar_score),
            ('Spelling', attempt.spelling_score),
            ('Punctuation', attempt.punctuation_score),
            ('Readability', attempt.readability_score),
            ('Vocabulary', attempt.vocabulary_score),
            ('Structure', attempt.structure_score),
            ('Relevance', attempt.relevance_score),
        ]
        for cat, score in categories:
            if score is not None and score >= 80:
                strengths.append(cat)
            elif score is not None and score < 60:
                weaknesses.append(cat)
        return render(request, 'essays/essay_results.html', {
            'attempt': attempt,
            'categories': categories,
            'strengths': strengths,
            'weaknesses': weaknesses,
        })

class SubmitEssayView(LoginRequiredMixin, View):
    def post(self, request, id):
        attempt = get_object_or_404(EssayAttempt, id=id)
        if attempt.user != request.user:
            return HttpResponseForbidden('Not allowed.')
        if not attempt.can_edit():
            return HttpResponseForbidden('Cannot submit. Essay is not editable.')
        # Update content and counts from POST
        content = request.POST.get('content', '')
        attempt.content = content
        attempt.word_count = calculate_word_count(content)
        attempt.character_count = calculate_character_count(content)
        attempt.paragraph_count = calculate_paragraph_count(content)
        # Validate timer
        if attempt.is_timed and attempt.is_time_expired():
            attempt.status = EssayAttempt.StatusChoices.SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['content', 'word_count', 'character_count', 'paragraph_count', 'status', 'submitted_at', 'updated_at'])
            return redirect('essays:essay_editor', attempt.id)
        # Validate minimum words
        validation = validate_essay_content(attempt.content, attempt.essay_topic)
        if not validation['valid']:
            return render(request, 'essays/essay_editor.html', {
                'attempt': attempt,
                'topic': attempt.essay_topic,
                'time_remaining': attempt.get_time_remaining(),
                'validation': validation,
                'can_edit': attempt.can_edit(),
                'error': 'Essay does not meet minimum requirements.'
            })
        attempt.status = EssayAttempt.StatusChoices.SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['content', 'word_count', 'character_count', 'paragraph_count', 'status', 'submitted_at', 'updated_at'])
        # --- Synchronous scoring ---
        EssayScorer().score_essay(attempt)
        return redirect('essays:essay_results', attempt.id)

# Proctored essay start from curriculum topic (for topic_detail.html integration)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

class EssayAttemptStartFromTopicView(LoginRequiredMixin, View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, topic_id):
        user = request.user
        from .models import EssayTopic, EssayAttempt
        from curriculum.models import Topic as CurriculumTopic
        curriculum_topic = get_object_or_404(CurriculumTopic, id=topic_id)
        essay_topic = curriculum_topic.essay_topic
        if not essay_topic:
            return render(request, 'essays/placeholder.html', {'error': 'No EssayTopic linked to this topic.'})
        if not essay_topic.is_active:
            return render(request, 'essays/placeholder.html', {'error': 'Selected EssayTopic is not active.'})
        # Enforce attempt limits, proctoring, etc.
        last_attempt = EssayAttempt.objects.filter(user=user, essay_topic=essay_topic).order_by('-attempt_number').first()
        max_attempts = getattr(essay_topic, 'max_attempts', 3)
        attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1
        if last_attempt and last_attempt.attempt_number >= max_attempts:
            return render(request, 'essays/attempts_exceeded.html', {'topic': essay_topic, 'max_attempts': max_attempts})
        attempt = EssayAttempt.objects.create(
            user=user,
            essay_topic=essay_topic,
            attempt_number=attempt_number,
            status=EssayAttempt.StatusChoices.IN_PROGRESS,
            time_limit_seconds=essay_topic.time_limit_minutes * 60,
            ip_address=self._get_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return redirect('essays:essay_editor', attempt.id)

    def _get_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class ForceExitEssayView(LoginRequiredMixin, View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, id):
        from .models import EssayAttempt
        attempt = get_object_or_404(EssayAttempt, id=id)
        if attempt.user != request.user:
            return JsonResponse({'error': 'Not allowed.'}, status=403)
        # Mark as cancelled/violated
        attempt.status = EssayAttempt.StatusChoices.CANCELLED if hasattr(EssayAttempt.StatusChoices, 'CANCELLED') else EssayAttempt.StatusChoices.SUBMITTED
        attempt.final_score = 0
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['status', 'final_score', 'submitted_at', 'updated_at'])
        # Redirect to results page with violation flag
        from django.urls import reverse
        redirect_url = reverse('essays:essay_results', args=[attempt.id]) + '?violation=1'
        return JsonResponse({'redirect_url': redirect_url})

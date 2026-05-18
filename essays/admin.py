

from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils.html import format_html
from django import forms
from .models import EssayTopic, EssayAttempt, EssayDraft, EssayAnalytics
from .services.ai_service import AIService



class EssayTopicAdminForm(forms.ModelForm):
	class Meta:
		model = EssayTopic
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Only set readonly if field exists (prevents KeyError)
		if 'semantic_keywords' in self.fields:
			self.fields['semantic_keywords'].widget.attrs['readonly'] = True


@admin.register(EssayTopic)
class EssayTopicAdmin(admin.ModelAdmin):
	form = EssayTopicAdminForm
	list_display = ('title', 'difficulty_level', 'min_words', 'max_words', 'time_limit_minutes', 'is_active', 'created_by', 'created_at')
	search_fields = ('title', 'description', 'instructions')
	list_filter = ('difficulty_level', 'is_active', 'created_at', 'updated_at')
	readonly_fields = ('created_at', 'updated_at', 'created_by', 'generate_keywords_button', 'semantic_keywords')
	ordering = ('-created_at',)

	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path('<int:object_id>/generate_keywords/', self.admin_site.admin_view(self.generate_keywords), name='essays_essaytopic_generate_keywords'),
		]
		return custom_urls + urls

	def generate_keywords_button(self, obj):
		if obj and obj.pk:
			return format_html(
				'<a class="button" href="{}">Generate AI Keywords</a>',
				f'../generate_keywords/'
			)
		return "(Save topic first)"
	generate_keywords_button.short_description = "Generate AI Keywords"

	def generate_keywords(self, request, object_id, *args, **kwargs):
		topic = self.get_object(request, object_id)
		if not topic:
			self.message_user(request, "Topic not found.", level=messages.ERROR)
			return HttpResponseRedirect("../")
		topic_text = topic.title
		if getattr(topic, "instructions", None):
			topic_text += "\n" + topic.instructions
		try:
			keywords = AIService.extract_keywords(topic_text)
			if not isinstance(keywords, list):
				keywords = []
			topic.semantic_keywords = keywords
			topic.save(update_fields=["semantic_keywords"])
			self.message_user(request, f"AI keywords generated and saved: {keywords}", level=messages.SUCCESS)
		except Exception as e:
			topic.semantic_keywords = []
			topic.save(update_fields=["semantic_keywords"])
			self.message_user(request, f"AI keyword generation failed: {e}", level=messages.ERROR)
		return HttpResponseRedirect("../")


@admin.register(EssayAttempt)
class EssayAttemptAdmin(admin.ModelAdmin):
	list_display = (
		'user', 'essay_topic', 'attempt_number', 'status', 'word_count', 'final_score',
		'grading_status', 'is_timed', 'timer_expired', 'created_at',
		'get_suspicious', 'get_risk_score'
	)
	search_fields = ('user__username', 'essay_topic__title', 'status', 'grading_status', 'ip_address', 'user_agent')
	list_filter = ('status', 'grading_status', 'is_timed', 'timer_expired', 'created_at', 'updated_at')
	readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'graded_at')

	ordering = ('-created_at',)
	actions = ['reset_attempts_for_selected']

	def reset_attempts_for_selected(self, request, queryset):
		# Group by user and essay_topic
		from collections import defaultdict
		grouped = defaultdict(list)
		for attempt in queryset:
			grouped[(attempt.user_id, attempt.essay_topic_id)].append(attempt)
		total = 0
		for (user_id, essay_topic_id), attempts in grouped.items():
			# Delete all attempts for this user/topic
			EssayAttempt.objects.filter(user_id=user_id, essay_topic_id=essay_topic_id).delete()
			total += len(attempts)
		self.message_user(request, f"Reset (deleted) all attempts for {len(grouped)} user/essay combinations. Total attempts deleted: {total}")
	reset_attempts_for_selected.short_description = "Reset (delete) all attempts for selected user/essay topics"

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		return qs.select_related('user', 'essay_topic', 'analytics')

	def get_suspicious(self, obj):
		return getattr(obj.analytics, 'suspicious_activity', False) if hasattr(obj, 'analytics') else False
	get_suspicious.boolean = True
	get_suspicious.short_description = 'Suspicious?'

	def get_risk_score(self, obj):
		return getattr(obj.analytics, 'risk_score', 0) if hasattr(obj, 'analytics') else 0
	get_risk_score.short_description = 'Risk Score'


@admin.register(EssayDraft)
class EssayDraftAdmin(admin.ModelAdmin):
	list_display = ('essay_attempt', 'word_count', 'saved_at')
	search_fields = ('essay_attempt__id',)
	ordering = ('-saved_at',)


@admin.register(EssayAnalytics)
class EssayAnalyticsAdmin(admin.ModelAdmin):
	list_display = ('essay_attempt', 'typing_events', 'paste_events', 'copy_events', 'delete_events', 'focus_loss_count', 'suspicious_activity', 'risk_score', 'updated_at')
	search_fields = ('essay_attempt__id',)
	ordering = ('-updated_at',)

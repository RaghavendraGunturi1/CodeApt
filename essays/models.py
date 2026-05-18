from django.db import models

class EssayDraft(models.Model):
	essay_attempt = models.ForeignKey('EssayAttempt', on_delete=models.CASCADE, related_name='drafts')
	content = models.TextField()
	word_count = models.PositiveIntegerField(default=0)
	saved_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-saved_at']
		indexes = [
			models.Index(fields=['essay_attempt', 'saved_at']),
		]

	def __str__(self):
		return f"Draft for Attempt {self.essay_attempt_id} at {self.saved_at}"


class EssayAnalytics(models.Model):
	essay_attempt = models.OneToOneField('EssayAttempt', on_delete=models.CASCADE, related_name='analytics')
	typing_events = models.PositiveIntegerField(default=0)
	paste_events = models.PositiveIntegerField(default=0)
	copy_events = models.PositiveIntegerField(default=0)
	delete_events = models.PositiveIntegerField(default=0)
	focus_loss_count = models.PositiveIntegerField(default=0)
	inactivity_seconds = models.PositiveIntegerField(default=0)
	longest_pause_seconds = models.PositiveIntegerField(default=0)
	suspicious_activity = models.BooleanField(default=False, db_index=True)
	risk_score = models.FloatField(default=0)
	last_activity_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=['suspicious_activity']),
			models.Index(fields=['risk_score']),
		]

	def __str__(self):
		return f"Analytics for Attempt {self.essay_attempt_id}"

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class EssayTopic(models.Model):
	class DifficultyLevel(models.IntegerChoices):
		BEGINNER = 1, 'Beginner'
		INTERMEDIATE = 2, 'Intermediate'
		ADVANCED = 3, 'Advanced'

	title = models.CharField(max_length=200, unique=True, db_index=True)
	description = models.TextField()
	instructions = models.TextField()
	difficulty_level = models.IntegerField(choices=DifficultyLevel.choices)
	min_words = models.PositiveIntegerField(default=250)
	max_words = models.PositiveIntegerField(default=1000)
	time_limit_minutes = models.PositiveIntegerField(default=30)
	is_active = models.BooleanField(default=True, db_index=True)
	created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_essay_topics')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	semantic_keywords = models.JSONField(default=list, blank=True)

	class Meta:
		ordering = ['-created_at']
		verbose_name = 'Essay Topic'
		verbose_name_plural = 'Essay Topics'

	def __str__(self):
		return self.title

	def is_available(self):
		return self.is_active

	def validate_word_count(self, word_count):
		return self.min_words <= word_count <= self.max_words

	def clean(self):
		super().clean()
		if self.min_words >= self.max_words:
			raise models.ValidationError('Minimum words must be less than maximum words.')
		if self.time_limit_minutes <= 0:
			raise models.ValidationError('Time limit must be greater than zero.')


class EssayAttempt(models.Model):
	class StatusChoices(models.TextChoices):
		DRAFT = 'DRAFT', 'Draft'
		IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
		SUBMITTED = 'SUBMITTED', 'Submitted'
		UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
		GRADED = 'GRADED', 'Graded'
		CANCELLED = 'CANCELLED', 'Cancelled'

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='essay_attempts')
	essay_topic = models.ForeignKey(EssayTopic, on_delete=models.CASCADE, related_name='attempts')
	attempt_number = models.PositiveIntegerField()
	status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT, db_index=True)
	content = models.TextField(blank=True)
	word_count = models.PositiveIntegerField(default=0)
	character_count = models.PositiveIntegerField(default=0)
	paragraph_count = models.PositiveIntegerField(default=0)
	started_at = models.DateTimeField(auto_now_add=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	graded_at = models.DateTimeField(null=True, blank=True)
	time_limit_seconds = models.PositiveIntegerField()
	is_timed = models.BooleanField(default=True)
	timer_expired = models.BooleanField(default=False)
	final_score = models.FloatField(null=True, blank=True)
	grammar_score = models.FloatField(null=True, blank=True)
	spelling_score = models.FloatField(null=True, blank=True)
	punctuation_score = models.FloatField(null=True, blank=True)
	readability_score = models.FloatField(null=True, blank=True)
	vocabulary_score = models.FloatField(null=True, blank=True)
	structure_score = models.FloatField(null=True, blank=True)
	relevance_score = models.FloatField(null=True, blank=True)
	grading_status = models.CharField(max_length=20, default='pending', db_index=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	user_agent = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']
		unique_together = [['user', 'essay_topic', 'attempt_number']]
		indexes = [
			models.Index(fields=['user', 'status']),
			models.Index(fields=['essay_topic', 'status']),
			models.Index(fields=['grading_status', 'status']),
			models.Index(fields=['created_at']),
		]

	def __str__(self):
		return f"EssayAttempt(user={self.user}, topic={self.essay_topic}, attempt={self.attempt_number})"

	def calculate_word_count(self):
		if self.content:
			words = self.content.split()
			return len(words)
		return 0

	def get_time_remaining(self):
		if not self.is_timed or not self.started_at:
			return None
		elapsed = (timezone.now() - self.started_at).total_seconds()
		return max(self.time_limit_seconds - int(elapsed), 0)

	def is_time_expired(self):
		remaining = self.get_time_remaining()
		return remaining is not None and remaining <= 0

	def can_edit(self):
		return self.status in [self.StatusChoices.DRAFT, self.StatusChoices.IN_PROGRESS] and not self.is_time_expired()

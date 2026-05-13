from django.db import models

# Create your models here.

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


# --- ASYNC EXECUTION JOB TRACKING ---
from django.utils import timezone
import uuid

class ExecutionJob(models.Model):
    JOB_TYPE_CHOICES = [
        ('assessment', 'Assessment'),
        ('practice', 'Practice'),
    ]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    related_id = models.CharField(max_length=64, blank=True, null=True, help_text="Related object (e.g. attempt id, submission id)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    queue_name = models.CharField(max_length=32, default='default')
    retries = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    log = models.TextField(blank=True, default='')


    def mark_processing(self):
        if self.status not in ['queued', 'processing']:
            return
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self, result):
        if self.status not in ['processing', 'queued']:
            return
        self.status = 'completed'
        self.finished_at = timezone.now()
        self.result = result
        self.save(update_fields=['status', 'finished_at', 'result'])

    def mark_failed(self, error):
        if self.status not in ['processing', 'queued']:
            return
        self.status = 'failed'
        self.finished_at = timezone.now()
        self.error = error
        self.save(update_fields=['status', 'finished_at', 'error'])

    def mark_cancelled(self, reason=None):
        if self.status not in ['queued', 'processing']:
            return
        self.status = 'cancelled'
        self.finished_at = timezone.now()
        if reason:
            self.error = reason
        self.save(update_fields=['status', 'finished_at', 'error'])

    def mark_timeout(self, reason=None):
        if self.status not in ['processing', 'queued']:
            return
        self.status = 'timeout'
        self.finished_at = timezone.now()
        if reason:
            self.error = reason
        self.save(update_fields=['status', 'finished_at', 'error'])

    def __str__(self):
        return f"{self.get_job_type_display()} | {self.status} | {self.id}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100, blank=True, help_text="Name to appear on Certificates")
    college_name = models.CharField(max_length=200, blank=True)
    roll_number = models.CharField(max_length=50, blank=True, null=True, help_text="University Roll Number")
    phone_number = models.CharField(max_length=15, blank=True)
    state = models.CharField(max_length=100, blank=True, null=True) # Added State
    bio = models.TextField(max_length=500, blank=True)
    avatar_url = models.URLField(blank=True, max_length=500, default="https://ui-avatars.com/api/?background=0D8ABC&color=fff&name=User")
    force_password_change = models.BooleanField(default=False, help_text="If true, forces user to reset password on next login.")

    def __str__(self):
        return f"{self.user.username}'s Profile"

# --- AUTOMATION: Auto-create Profile when User is created ---
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Default avatar based on username
        default_avatar = f"https://ui-avatars.com/api/?background=0D8ABC&color=fff&name={instance.username}"
        Profile.objects.create(user=instance, avatar_url=default_avatar)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
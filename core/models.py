# --- ASYNC EXECUTION JOB TRACKING ---
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

class ExecutionJob(models.Model):
    QUEUE_CHOICES = [
        ("assessment", "Assessment"),
        ("practice", "Practice"),
    ]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    job_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    submission_ref = models.CharField(max_length=128, blank=True, null=True, help_text="Submission or attempt reference")
    queue = models.CharField(max_length=32, choices=QUEUE_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="queued")
    result = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.job_id} ({self.queue}) - {self.status}"
from django.db import models

# Create your models here.

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# ... (keep your existing models) ...

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
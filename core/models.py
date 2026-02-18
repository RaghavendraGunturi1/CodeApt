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
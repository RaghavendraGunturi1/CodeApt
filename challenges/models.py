from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class DailyQuestion(models.Model):
    TYPE_CHOICES = (
        ('MCQ', 'Multiple Choice'),
        ('CODE', 'Coding Challenge'),
    )
    
    question_type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    release_date = models.DateField(unique=True, help_text="The date this question goes live")
    
    # MCQ Fields (can be null if type is CODE)
    option_a = models.CharField(max_length=200, blank=True, null=True)
    option_b = models.CharField(max_length=200, blank=True, null=True)
    option_c = models.CharField(max_length=200, blank=True, null=True)
    option_d = models.CharField(max_length=200, blank=True, null=True)
    correct_option = models.CharField(max_length=10, choices=[('A','A'), ('B','B'), ('C','C'), ('D','D')], blank=True, null=True)

    def __str__(self):
        return f"{self.release_date} - {self.title}"

class TestCase(models.Model):
    """Stores 5 test cases for Coding Questions"""
    question = models.ForeignKey(DailyQuestion, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField()

    def __str__(self):
        return f"Test Case for {self.question.title}"

class UserStreak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak')
    current_streak = models.IntegerField(default=0)
    max_streak = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    last_solved_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - Streak: {self.current_streak}"

class DailySubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(DailyQuestion, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question') # User can only submit once for points
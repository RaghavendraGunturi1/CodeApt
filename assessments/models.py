from django.db import models
from django.contrib.auth.models import User
from curriculum.models import Topic

class Exam(models.Model):
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE, related_name='exam')
    duration_minutes = models.IntegerField(default=60)
    pass_percentage = models.IntegerField(default=50)
    total_marks = models.IntegerField(default=100)
    
    def __str__(self):
        return f"Exam: {self.topic.name}"

class ExamQuestion(models.Model):
    TYPE_CHOICES = (
        ('MCQ_SINGLE', 'Single Choice'),
        ('MCQ_MULTI', 'Multiple Choice'),
        ('CODE', 'Coding Challenge'),
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    q_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    text = models.TextField()
    marks = models.IntegerField(default=5)
    
    # Options for MCQs (Stored as simple text fields for simplicity, or JSON)
    option_1 = models.CharField(max_length=255, blank=True, null=True)
    option_2 = models.CharField(max_length=255, blank=True, null=True)
    option_3 = models.CharField(max_length=255, blank=True, null=True)
    option_4 = models.CharField(max_length=255, blank=True, null=True)
    option_5 = models.CharField(max_length=255, blank=True, null=True)
    
    # Answers
    # For Single: "1"
    # For Multi: "1,3" (Comma separated)
    correct_options = models.CharField(max_length=10, blank=True, null=True, help_text="For Multi, separate with comma e.g. '1,3'")
    
    # Coding Fields
    starter_code = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.text[:50]

class ExamTestCase(models.Model):
    """Test cases for Coding Questions in Exam"""
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField()

class StudentExamAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)
    response_data = models.JSONField(default=dict, blank=True, help_text="Stores user answers {question_id: answer}")
    
    # Proctoring Data
    warnings_triggered = models.IntegerField(default=0)
    is_auto_submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.exam.topic.name}"
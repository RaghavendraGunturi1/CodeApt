from django.db import models
from django.contrib.auth.models import User
from curriculum.models import Topic
from django.utils import timezone

class Exam(models.Model):
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE, related_name='exam')
    total_marks = models.IntegerField(default=100)
    pass_percentage = models.IntegerField(default=50)
    # Note: 'duration_minutes' is removed here as it is now handled per section
    
    def __str__(self):
        return self.topic.name

class ExamSection(models.Model):
    """
    Groups questions into time-bound sections.
    Example: 'Part A - Numerical Ability' (20 mins), 'Part B - Coding' (45 mins)
    """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=100)
    order = models.IntegerField(default=1)   # Defines the sequence (1, 2, 3...)
    duration_minutes = models.IntegerField(help_text="Time allocated for this specific section")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.exam} - {self.name}"

class ExamQuestion(models.Model):
    TYPE_CHOICES = (
        ('MCQ_SINGLE', 'Single Choice'),
        ('MCQ_MULTI', 'Multiple Choice'),
        ('CODE', 'Coding Challenge'),
    )
    
    # CHANGED: Questions now belong to a Section, not directly to the Exam
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name='questions',null=True, blank=True)
    
    q_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    text = models.TextField(blank=True, null=True, help_text="Question text (Optional if using an image)")
    image = models.ImageField(upload_to='exam_images/', blank=True, null=True, help_text="Upload an image if the question requires one (e.g. Geometry figures)")
    marks = models.IntegerField(default=5)
    
    # Options for MCQs
    option_1 = models.CharField(max_length=255, blank=True, null=True)
    option_2 = models.CharField(max_length=255, blank=True, null=True)
    option_3 = models.CharField(max_length=255, blank=True, null=True)
    option_4 = models.CharField(max_length=255, blank=True, null=True)
    option_5 = models.CharField(max_length=255, blank=True, null=True)
    
    # Correct Answers
    # Single: "1"
    # Multi: "1,3"
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
    
    # NEW: Section Tracking Logic
    current_section = models.ForeignKey(ExamSection, on_delete=models.SET_NULL, null=True, blank=True)
    section_start_time = models.DateTimeField(null=True, blank=True)
    
    # Storage for user answers
    # Structure: { "section_id": { "question_id": "answer_value" } }
    response_data = models.JSONField(default=dict, blank=True, help_text="Stores structured user answers")
    
    # Proctoring Data
    warnings_triggered = models.IntegerField(default=0)
    is_auto_submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.exam.topic.name}"
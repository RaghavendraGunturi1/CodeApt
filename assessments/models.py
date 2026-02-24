from django.db import models
from django.contrib.auth.models import User
from curriculum.models import Topic
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

class Exam(models.Model):
    topic = models.OneToOneField(Topic, on_delete=models.CASCADE, related_name='exam')
    total_marks = models.IntegerField(default=100)
    pass_percentage = models.IntegerField(default=50)
    # Note: 'duration_minutes' is removed here as it is now handled per section
    
    # --- Fix 1: Inside the Exam class ---
    def __str__(self):
        try:
            return self.topic.name
        except (AttributeError, ObjectDoesNotExist):
            return f"Exam ID: {self.id} (Missing Topic)"


import uuid

class PublicExamLink(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_available(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    def __str__(self):
        return f"Public Link - {self.exam.topic.name}"

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

    # --- Fix 2: Inside the ExamSection class ---
    def __str__(self):
        try:
            # We call str(self.exam) to trigger the defensive check above
            return f"{self.exam} - {self.name}"
        except Exception:
            return f"Section: {self.name} (Orphaned)"

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
    from cloudinary_storage.storage import MediaCloudinaryStorage

    image = models.ImageField(
        upload_to='exam_images/',
        storage=MediaCloudinaryStorage(),
        blank=True,
        null=True
    )
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
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # 🔥 NEW: Track which public link created this attempt
    public_link = models.ForeignKey(
        'PublicExamLink',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attempts"
    )

    # Public fields
    roll_number = models.CharField(max_length=100, null=True, blank=True)
    college_name = models.CharField(max_length=255, null=True, blank=True)

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    score = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)

    current_section = models.ForeignKey(
        ExamSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    section_start_time = models.DateTimeField(null=True, blank=True)

    response_data = models.JSONField(default=dict, blank=True)

    warnings_triggered = models.IntegerField(default=0)
    is_auto_submitted = models.BooleanField(default=False)

    # 🔥 Helper property (clean public detection)
    @property
    def is_public(self):
        return self.user is None

    def __str__(self):
        if self.user:
            user_part = self.user.username
        else:
            user_part = f"Public({self.roll_number})"

        exam_part = self.exam.topic.name if self.exam and self.exam.topic else "Unknown Exam"

        return f"{user_part} - {exam_part}"
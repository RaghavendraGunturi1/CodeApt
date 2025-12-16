from django.db import models
from django.utils.text import slugify

class Program(models.Model):
    name = models.CharField(max_length=100)  # e.g., "Technical Training"
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Subject(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    
    # NEW FIELDS FOR COURSE PAGE
    image = models.ImageField(upload_to='subjects/', blank=True, null=True)
    description = models.TextField(blank=True, help_text="Short summary for the course card")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="If set, shows original price with strikethrough")
    is_popular = models.BooleanField(default=False) # To show a "Bestseller" badge
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Topic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=200) # e.g., "Lists & Tuples"
    order = models.PositiveIntegerField(default=0)
    TOPIC_TYPES = (
        ('text', 'Text Article'),
        ('video', 'Video Lesson'),
        ('quiz', 'Quiz'),
    )
    topic_type = models.CharField(max_length=10, choices=TOPIC_TYPES, default='text')
    
    # Content for Text Lessons
    content = models.TextField(blank=True, help_text="Main content for text lessons")
    
    # Video ID for Video Lessons (e.g., "dQw4w9WgXcQ" from youtube.com/watch?v=dQw4w9WgXcQ)
    video_id = models.CharField(max_length=20, blank=True, help_text="YouTube Video ID (e.g., dQw4w9WgXcQ)")
    
    # Duration (e.g., "10 mins")
    duration = models.CharField(max_length=50, blank=True, help_text="Estimated time to complete")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.subject.name} - {self.name}"


class Question(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    
    def __str__(self):
        return self.text[:50]

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        return self.text

    
from django.contrib.auth.models import User  # Ensure this is at the top


class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'subject')  # Prevents duplicate enrollments

    def __str__(self):
        return f"{self.user.username} - {self.subject.name}"


# Add this at the bottom of curriculum/models.py

class TopicProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='topic_progress')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'topic')  # Ensures one record per user per topic

    def __str__(self):
        status = "Done" if self.is_completed else "Pending"
        return f"{self.user.username} - {self.topic.name} ({status})"


# Add at the bottom of curriculum/models.py

class QuizSubmission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_submissions')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quiz_submissions')
    score = models.IntegerField()
    total_questions = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at'] # Newest first

    def __str__(self):
        return f"{self.user.username} - {self.subject.name}: {self.score}/{self.total_questions}"
        
    @property
    def percentage(self):
        if self.total_questions == 0:
            return 0
        return int((self.score / self.total_questions) * 100)


# In curriculum/models.py (At the bottom)

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='orders')
    order_id = models.CharField(max_length=100, unique=True) # Our internal ID
    transaction_id = models.CharField(max_length=100, blank=True, null=True) # PhonePe ID
    amount = models.DecimalField(max_digits=10, decimal_places=2) # Store exact amount paid
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_id} - {self.user.username}"
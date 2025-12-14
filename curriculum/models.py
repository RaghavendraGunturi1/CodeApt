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
    content = models.TextField(help_text="Main content for this topic")
    order = models.PositiveIntegerField(default=0)

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
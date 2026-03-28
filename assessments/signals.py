from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Exam, ExamAttemptCounter


@receiver(post_save, sender=User)
def create_counters_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return

    exams = Exam.objects.all().only("id")
    counters = [
        ExamAttemptCounter(user=instance, exam=exam, attempt_count=0)
        for exam in exams
    ]
    if counters:
        ExamAttemptCounter.objects.bulk_create(counters, ignore_conflicts=True)


@receiver(post_save, sender=Exam)
def create_counters_for_new_exam(sender, instance, created, **kwargs):
    if not created:
        return

    users = User.objects.all().only("id")
    counters = [
        ExamAttemptCounter(user=user, exam=instance, attempt_count=0)
        for user in users
    ]
    if counters:
        ExamAttemptCounter.objects.bulk_create(counters, ignore_conflicts=True)

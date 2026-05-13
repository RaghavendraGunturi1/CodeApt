from django.test import TestCase
from django.contrib.auth import get_user_model
from assessments.models import Exam, ExamSection, ExamQuestion, StudentExamAttempt
from core.execution_queue import enqueue_grading_job
from django.utils import timezone
from django.db import transaction

User = get_user_model()

class GradingIdempotencyTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.exam = Exam.objects.create(topic_id=1, total_marks=100, pass_percentage=40, max_attempts=2)
        self.section = ExamSection.objects.create(exam=self.exam, name='Section 1', order=1, duration_minutes=10)
        self.question = ExamQuestion.objects.create(section=self.section, q_type='MCQ_SINGLE', text='Q1', marks=5, correct_options='1', option_1='A', option_2='B', option_3='C', option_4='D')
        self.attempt = StudentExamAttempt.objects.create(user=self.user, exam=self.exam, current_section=self.section, section_start_time=timezone.now())
        self.attempt.response_data = {str(self.section.id): {str(self.question.id): '1'}}
        self.attempt.completed_at = timezone.now()
        self.attempt.save()

    def test_grading_idempotency(self):
        # Enqueue grading job twice
        enqueue_grading_job(self.attempt.id)
        enqueue_grading_job(self.attempt.id)
        # Simulate worker running job twice (should not double-grade)
        from core.execution_queue import execute_grading_job_worker
        execute_grading_job_worker(self.attempt.id)
        execute_grading_job_worker(self.attempt.id)
        # Reload attempt
        attempt = StudentExamAttempt.objects.get(id=self.attempt.id)
        self.assertEqual(attempt.grading_status, 'DONE')
        self.assertGreaterEqual(attempt.score, 0)
        # Score should not be incremented twice
        score1 = attempt.score
        execute_grading_job_worker(self.attempt.id)
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, score1)

    def test_atomicity_under_concurrency(self):
        # Simulate two concurrent grading jobs
        def grade():
            execute_grading_job_worker(self.attempt.id)
        import threading
        t1 = threading.Thread(target=grade)
        t2 = threading.Thread(target=grade)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        attempt = StudentExamAttempt.objects.get(id=self.attempt.id)
        self.assertEqual(attempt.grading_status, 'DONE')
        self.assertGreaterEqual(attempt.score, 0)

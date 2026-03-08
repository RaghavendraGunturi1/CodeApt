from django.contrib.auth.models import User
from curriculum.models import TopicProgress, QuizSubmission, Topic
from assessments.models import StudentExamAttempt, Exam
from challenges.models import UserStreak

# Get a valid college name to test
u = User.objects.exclude(profile__college_name='').first()
if not u:
    print("No users with college names found.")
else:
    cn = u.profile.college_name
    print(f"Testing for college: {cn}")
    users = User.objects.filter(profile__college_name=cn)
    
    for user in users[:5]:
        total_topics = TopicProgress.objects.filter(user=user, is_completed=True).count()
        quizzes = QuizSubmission.objects.filter(user=user).count()
        attempts = StudentExamAttempt.objects.filter(user=user).count()
        
        print(f"User: {user.username} | Topics: {total_topics} | Quizzes: {quizzes} | Exams: {attempts}")

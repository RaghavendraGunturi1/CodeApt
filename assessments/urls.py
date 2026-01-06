# assessments/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # The page where the user reads instructions and enters fullscreen
    path('start/<int:topic_id>/', views.start_exam, name='start_exam'),
    
    # The API endpoint that saves the exam answers
    path('submit/<int:attempt_id>/', views.submit_exam, name='submit_exam'),
    path('check_code/<int:question_id>/', views.check_code, name='check_code'),
    # Reports & History (These are likely missing in your file)
    path('history/', views.exam_history, name='exam_history'),
    path('result/<int:attempt_id>/', views.attempt_detail, name='attempt_detail'),
]
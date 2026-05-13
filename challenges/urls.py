from django.urls import path
from . import views

urlpatterns = [
    path('daily/', views.daily_challenge, name='daily_challenge'),
    path('daily/submit-mcq/<int:question_id>/', views.submit_mcq, name='submit_mcq'),
    path('daily/submit-code/<int:question_id>/', views.submit_code, name='submit_code'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]
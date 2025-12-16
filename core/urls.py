from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'), # Added this line
    path('training/', views.training, name='training'), # Added this line
    path('placements/', views.placements, name='placements'),
    path('about/', views.about, name='about'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('course/<slug:slug>/', views.course_detail, name='course_detail'),
    path('topic/<int:topic_id>/', views.topic_detail, name='topic_detail'),
    path('arena/', views.arena, name='arena'),
    path('run_code/', views.run_code, name='run_code'),
    path('quiz/<slug:slug>/', views.quiz_view, name='quiz'),
    path('courses/', views.courses, name='courses'),
    path('course-overview/<slug:slug>/', views.course_landing, name='course_landing'),
    path('enroll/<slug:slug>/', views.enroll_course, name='enroll_course'),
    path('toggle-progress/<int:topic_id>/', views.toggle_topic_completion, name='toggle_progress'),
    path('profile/', views.profile, name='profile'),
    path('buy/<slug:subject_slug>/', views.initiate_payment, name='initiate_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
]
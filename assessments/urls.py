# assessments/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # The page where the user reads instructions and enters fullscreen
    path('start/<int:topic_id>/', views.start_exam, name='start_exam'),
    
    # CHANGED: We now submit sections, not the whole exam at once
    path('submit-section/<int:attempt_id>/', views.submit_section, name='submit_section'),
    
    # NEW: Load section data for seamless transitions
    path('load-section/<int:attempt_id>/', views.load_section_data, name='load_section'),
    
    # Utilities
    path('check_code/<int:question_id>/', views.check_code, name='check_code'),
    path('run_code/', views.run_code_piston, name='run_code'), # Ensure you have a generic run view or reuse check_code logic
    # Reports & History (These are likely missing in your file)
    path('history/', views.exam_history, name='exam_history'),
    path('result/<int:attempt_id>/', views.attempt_detail, name='attempt_detail'),
    path('result-status/<int:attempt_id>/', views.result_status, name='result_status'),
    path('run-test-cases/', views.run_question_test_cases, name='run_test_cases'),
    path(
        'public/<uuid:token>/',
        views.public_exam_entry,
        name='public_exam_entry'
    ),
    path(
        'public-start/<int:attempt_id>/',
        views.public_start_exam,
        name='public_start_exam'
    ),
]
# essays/urls.py
from django.urls import path

from .views import (
    EssayAttemptListView,
    EssayAttemptStartView,
    EssayAttemptStartFromTopicView,
    EssayEditorView,
    SaveDraftAjaxView,
    SubmitEssayView,
    EssayResultsView,
    EssayAnalyticsAjaxView,
    ForceExitEssayView,
)

from .views_ai_report import generate_ai_report
from .views_attempt_history import essay_attempt_history

app_name = "essays"
urlpatterns = [
    path('', EssayAttemptListView.as_view(), name='essay_list'),
    path('start/', EssayAttemptStartView.as_view(), name='essay_start'),
    path('start-from-topic/<int:topic_id>/', EssayAttemptStartFromTopicView.as_view(), name='start_from_topic'),
    path('<int:id>/editor/', EssayEditorView.as_view(), name='essay_editor'),
    path('<int:id>/save-draft/', SaveDraftAjaxView.as_view(), name='essay_save_draft'),
    path('<int:id>/analytics/', EssayAnalyticsAjaxView.as_view(), name='essay_analytics'),
    path('<int:id>/submit/', SubmitEssayView.as_view(), name='essay_submit'),
    path('<int:id>/results/', EssayResultsView.as_view(), name='essay_results'),
    path('<int:id>/force-exit/', ForceExitEssayView.as_view(), name='essay_force_exit'),
    path('generate-ai-report/', generate_ai_report, name='generate_ai_report'),
    path('history/', essay_attempt_history, name='essay_attempt_history'),
]

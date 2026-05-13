import django_rq
from django.contrib import admin
from django.urls import path, include  # Import include\
from core import views  # Import views to access the vision view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('django-rq/', django_rq.urls),
    path('', include('core.urls')),  # Connect core urls
    path('accounts/', include('accounts.urls')), # NEW LINE
    path('challenges/', include('challenges.urls')),
    path('assessments/', include('assessments.urls')),  # NEW LINE for assessments app
]
from django.urls import path, include
from django_rq import views as rq_views

urlpatterns = [
    path('django-rq/', rq_views.stats, name='django_rq_stats'),
]

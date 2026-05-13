import django_rq
from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # django-rq dashboard
    path('django-rq/', include(django_rq.urls)),

    # App routes
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('challenges/', include('challenges.urls')),
    path('assessments/', include('assessments.urls')),
]
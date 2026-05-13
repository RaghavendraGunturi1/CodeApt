
from django.contrib import admin
from django.urls import path, include
from rq_urls import urlpatterns as rq_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('challenges/', include('challenges.urls')),
    path('assessments/', include('assessments.urls')),
]
urlpatterns += rq_urlpatterns
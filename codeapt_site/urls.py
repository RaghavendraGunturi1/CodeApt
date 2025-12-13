from django.contrib import admin
from django.urls import path, include  # Import include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # Connect core urls
    path('accounts/', include('accounts.urls')), # NEW LINE
]
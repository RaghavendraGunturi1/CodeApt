#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import Profile
from django.test.client import encode_multipart
from django.contrib.auth import authenticate, login
from django.test import RequestFactory

# Get a college with students
colleges = Profile.objects.exclude(college_name='').values_list('college_name', flat=True).distinct()
college_name = colleges.first()

if college_name:
    print(f"Testing with college: {college_name}")
    
    # Create admin client
    client = Client()
    
    # Get or create an admin user
    admin_user = User.objects.filter(is_staff=True, is_superuser=True).first()
    if not admin_user:
        # Create admin if needed
        admin_user = User.objects.create_superuser('testadmin', 'admin@test.com', 'testpass123')
        print(f"Created admin user: {admin_user.username}")
    else:
        print(f"Using existing admin: {admin_user.username}")
    
    # Test direct login with known password first
    print("\nTesting direct function call instead of HTTP POST...")
    try:
        # Import the view function directly
        from core.admin import UserAdmin
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.post('/admin/auth/user/export_performance/', 
                              {'college_name': [college_name]})
        request.user = admin_user
        request.session = client.session if hasattr(client, 'session') else {}
        
        # Create UserAdmin instance
        admin_site = AdminSite()
        user_admin = UserAdmin(User, admin_site)
        
        # Call the view directly
        response = user_admin.export_performance_view(request)
        
        print(f"Response type: {type(response)}")
        print(f"Response status: {response.status_code if hasattr(response, 'status_code') else 'N/A'}")
        
        if hasattr(response, 'get'):
            print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
            print(f"Content-Length: {len(response.content) if hasattr(response, 'content') else 'N/A'} bytes")
            
            if 'xlsx' in response.get('Content-Type', '').lower():
                print("[OK] Excel export successful!")
            else:
                print(f"[INFO] Content preview: {str(response.content)[:200]}")
        
    except Exception as e:
        print(f"[ERROR] Exception in direct call: {e}")
        import traceback
        traceback.print_exc()

else:
    print("No colleges found")

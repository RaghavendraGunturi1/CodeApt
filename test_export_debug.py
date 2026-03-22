#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import Profile

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
        admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'admin')
        print(f"Created admin user: {admin_user.username}")
    else:
        print(f"Using existing admin: {admin_user.username}")
    
    # Login as admin
    if client.login(username=admin_user.username, password='admin'):
        print("[OK] Logged in as admin")
    else:
        print("[WARN] Login failed with 'admin' password")
    
    # Try the export
    print(f"\nAttempting export for college: {college_name}")
    try:
        response = client.post('/admin/auth/user/export_performance/', 
                              {'college_name': [college_name]},
                              follow=True)
        print(f"Response status: {response.status_code}")
        content = response.content.decode('utf-8') if isinstance(response.content, bytes) else response.content
        print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
        print(f"Content preview (first 500 chars): {content[:500]}")
        
        if response.status_code == 200 and 'xlsx' in response.get('Content-Type', '').lower():
            print("[OK] Export successful!")
            print(f"Content-Length: {len(response.content)} bytes")
        elif 'error' in content.lower() or 'traceback' in content.lower():
            print("[ERROR] Found error in response:")
            print(content)
        else:
            print("[WARN] Got HTML form back instead of Excel file")
            # Check if form is present
            if 'college_name' in content:
                print("Form detected - POST may not have been processed")
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No colleges found")

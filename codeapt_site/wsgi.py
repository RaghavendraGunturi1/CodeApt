import os
import sys
import subprocess
from django.core.wsgi import get_wsgi_application

# 1. Path Resolution: Add the current directory to sys.path
# This ensures that libraries installed with '--target .' during build are found.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 2. Environment Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')

# 3. Automation for AWS Startup
# This runs only once when the App Runner instance wakes up.
if os.environ.get('AWS_EXECUTION_ENV'):
    print("AWS Environment detected. Running startup tasks...")
    try:
        # Run database migrations
        subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
        # Collect static files for WhiteNoise/Cloudinary
        subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], check=True)
    except Exception as e:
        print(f"Startup task failed: {e}")

# 4. Standard WSGI Application
application = get_wsgi_application()
app = application # Alias for some deployment platforms
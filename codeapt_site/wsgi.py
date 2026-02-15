import os
import sys
import subprocess
from django.core.wsgi import get_wsgi_application

# 1. Path Setup: Ensure the app can find its own modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')

# 2. Automation for AWS Startup
if os.environ.get('AWS_EXECUTION_ENV'):
    # We run migrations and static collection here to ensure DB is ready
    try:
        subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"])
        subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"])
    except Exception as e:
        print(f"Startup tasks error: {e}")

application = get_wsgi_application()
app = application
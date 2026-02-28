import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')
django.setup()

from assessments.views import public_start_exam
from django.test import RequestFactory
from assessments.models import StudentExamAttempt

# 140 is the ID from the logs
attempt_id = 140
try:
    req = RequestFactory().get(f'/assessments/public-start/{attempt_id}/')
    req.session = {}
    
    # Try rendering
    resp = public_start_exam(req, attempt_id)
    print("STATUS CODE:", resp.status_code)
    print("RESPONSE LENGTH:", len(resp.content))
except Exception as e:
    traceback.print_exc()

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeapt_site.settings')
django.setup()

from django.test import Client

c = Client()
try:
    r = c.get('/assessments/public-start/131/')
    if r.status_code == 500:
        print("500 ERROR CAUGHT. CHECKING HTML...")
        print(r.content.decode('utf-8'))
    else:
        print(f"Status Code: {r.status_code}")
except Exception as e:
    import traceback
    traceback.print_exc()

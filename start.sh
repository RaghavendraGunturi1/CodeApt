#!/bin/bash

# 1. Install gunicorn and dependencies in the RUN container
python3 -m pip install gunicorn whitenoise dj-database-url psycopg2-binary cloudinary django-cloudinary-storage

# 2. Run Django setup tasks
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput

# 3. Start the server
python3 -m gunicorn --bind 0.0.0.0:8080 codeapt_site.wsgi:application
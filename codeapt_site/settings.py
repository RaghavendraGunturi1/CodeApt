import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- 1. SECURITY SETTINGS ---
# Pulls from AWS Environment Variables for safety
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-default-key-change-this')

# Set to False in AWS Environment
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Allow all hosts provided by AWS App Runner
ALLOWED_HOSTS = ['codeapt.in', 'www.codeapt.in', 'localhost', '127.0.0.1', '.vercel.app', '.awsapprunner.com']


# --- 2. DATABASE CONFIGURATION (NeonDB) ---
# Uses dj-database-url to parse the single connection string
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600, # Keeps connections open for better performance
        conn_health_checks=True,
        ssl_require=True
    )
}


# --- 3. STORAGE CONFIGURATION (Cloudinary & Static) ---
# WhiteNoise handles static files; Cloudinary handles your media/images
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Cloudinary credentials from Environment Variables
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}


# --- 4. STATIC FILES (WhiteNoise) ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']


# --- 5. MIDDLEWARE ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Must be exactly here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# --- 6. PHONEPE CONFIGURATION ---
PHONEPE_CLIENT_ID = os.environ.get("PHONEPE_CLIENT_ID")
PHONEPE_CLIENT_SECRET = os.environ.get("PHONEPE_CLIENT_SECRET")
PHONEPE_CLIENT_VERSION = int(os.environ.get("PHONEPE_CLIENT_VERSION", 1))
PHONEPE_ENV = os.environ.get("PHONEPE_ENV", "SANDBOX")


# --- REST OF YOUR CONFIGURATION ---
INSTALLED_APPS = [
    'core',
    'accounts',
    'curriculum',
    'challenges',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'assessments',
]

ROOT_URLCONF = 'codeapt_site.urls'
WSGI_APPLICATION = 'codeapt_site.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
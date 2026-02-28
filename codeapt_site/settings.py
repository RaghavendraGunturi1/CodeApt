import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 1. SECURITY SETTINGS ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-default-key-change-this')

# Set to False on App Runner to prevent leaking sensitive info
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    '*',
    'codeapt.in', 
    'www.codeapt.in', 
    '5cmypptmab.us-east-1.awsapprunner.com', 
    'localhost', 
    '127.0.0.1', 
    '.vercel.app', 
    '.awsapprunner.com'
]

# Required for Django 4.0+ to allow logins and form submissions from your domain
CSRF_TRUSTED_ORIGINS = [
    'https://codeapt.in',
    'https://www.codeapt.in',
    'https://5cmypptmab.us-east-1.awsapprunner.com'
]

# --- 2. APPLICATION DEFINITION ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Your Apps
    'core',
    'accounts',
    'curriculum',
    'challenges',
    'assessments',
    
    # Third Party
    'cloudinary_storage',
    'cloudinary',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Essential for AWS Static Files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'codeapt_site.urls'

# --- 3. TEMPLATES CONFIGURATION (CRITICAL FOR 500 ERROR FIX) ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'codeapt_site.wsgi.application'

# --- 4. DATABASE CONFIGURATION (NEON DB) ---
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL') or "postgresql://neondb_owner:npg_X5ntxVCyc9bQ@ep-icy-king-a121yr5z-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True
    )
}
# Force SSL mode for NeonDB
DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}

# --- 5. STATIC & MEDIA STORAGE (CLOUDINARY & WHITENOISE) ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise settings for production performance
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_NAME') or 'dpxj87q7w',
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY') or '874597924378788',
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET') or '21f209545123123123123123123123123',
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# --- 6. PHONEPE CONFIGURATION ---
PHONEPE_CLIENT_ID = os.environ.get("PHONEPE_CLIENT_ID")
PHONEPE_CLIENT_SECRET = os.environ.get("PHONEPE_CLIENT_SECRET")
PHONEPE_CLIENT_VERSION = int(os.environ.get("PHONEPE_CLIENT_VERSION", 1))
PHONEPE_ENV = os.environ.get("PHONEPE_ENV", "PRODUCTION")

# --- 7. MISC ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata' # Matches your Hyderabad location
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# Change this to False if it is True
SECURE_SSL_REDIRECT = False 

# Add this to help Django understand it's behind the AWS proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
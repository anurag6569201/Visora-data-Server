from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Secrets
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
VISIORA_BACKEND_SECRET_KEY = os.getenv('VISIORA_BACKEND_SECRET_KEY')

# Admin URL
ADMIN_SECRET_PATH_SEGMENT = os.getenv('DJANGO_ADMIN_SECRET_PATH')
ADMIN_URL_PREFIX = f'{ADMIN_SECRET_PATH_SEGMENT}/'

# Debug
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

# Hosts
ALLOWED_HOSTS = ['*']

# Installed Apps
INSTALLED_APPS = [
    'jazzmin',

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'import_export',

    # Local apps
    'landing',
    'staticdata',
    'visoraai',
    'visoraplanner',
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',

    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dataserver.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "dataserver.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Site ID
SITE_ID = 1

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Default Auto Field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER_EMAIL")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_USER_PASSWORD")
EMAIL_USE_TLS = True

# Account Settings
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none'
LOGIN_REDIRECT_URL = '/'

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with', 'x-anonymous-user-id',
]
CORS_ALLOW_METHODS = [
    'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT',
]

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = False

# Jazzmin Admin Settings
JAZZMIN_SETTINGS = {
    "site_title": "Visora",
    "site_header": "Visora Dashboard",
    "site_brand": "Visora",
    "site_logo": "../static/assets/img/logo.png",
    "login_logo": "../static/assets/img/logo.png",
    "welcome_sign": "Welcome to Visora Admin Panel",
    "copyright": "visora © 2024",
    "user_avatar": "profile.picture",
    "footer_links": [
        {"name": "Visora", "url": "https://visora.in", "new_window": True},
        {"name": "Support", "url": "mailto:support@gmail.com", "new_window": True},
    ],
    "custom_css": "../static/assets/css/jazzmin.css",
    "custom_js": "../static/assets/js/jazzmin.js",
}


# Logging (important)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
}

# Security (recommended for production)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG

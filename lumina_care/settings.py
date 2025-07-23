# lumina_care/settings.py
# -----------------------------------------------------------
# Django settings for Lumina Care LMS (multi‑tenant, JWT‑cookie)
# -----------------------------------------------------------

from pathlib import Path
from datetime import timedelta
import os
import sys
from logging.handlers import RotatingFileHandler

# FRONTEND URL
# -----------------------------------------------------------
FRONTEND_URL = 'http://localhost:5173'  # Define in uppercase, placed before CORS settings

# -----------------------------------------------------------
# BASE PATHS
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'talent_engine'))  # leave for fcntl stub on Windows

# -----------------------------------------------------------
# CORE SECURITY
# -----------------------------------------------------------
SECRET_KEY = 'django-insecure-!v)6(7@u983fg+8gdo1o)dr^59vvp3^ol*apr%c+$0n$#swz-1'
DEBUG = True                     # flip to True for local dev
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'complete-lms-api.onrender.com',

]

# -----------------------------------------------------------
# APPLICATIONS
# -----------------------------------------------------------
INSTALLED_APPS = [
    # third‑party
    'corsheaders',
    'django_tenants',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'django_crontab',

    # auth / social
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',

    # local
    'core',
    'courses',
    'users',
    'subscriptions',
    'schedule',
    'payments',
    'forum',
    'groups',
    'messaging',
    'advert',
]

SITE_ID = 1

# -----------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',          # must be first
    'lumina_care.middleware.CustomTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# -----------------------------------------------------------
# AUTHENTICATION & ACCOUNTS
# -----------------------------------------------------------
AUTH_USER_MODEL = 'users.CustomUser'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_METHOD = 'email'
ACCOUNT_SIGNUP_FIELDS = ['email', 'password1', 'password2']
SOCIALACCOUNT_AUTO_SIGNUP = True

SOCIALACCOUNT_PROVIDERS = {
    'google':   {'SCOPE': ['profile', 'email']},
    'apple':    {'APP': {'client_id': '', 'secret': '', 'key': '', 'certificate_key': ''}},
    'microsoft':{'APP': {'client_id': '', 'secret': '', 'tenant': 'common'},
                 'SCOPE': ['User.Read', 'email']},
}

# -----------------------------------------------------------
# DATABASE & TENANCY
# -----------------------------------------------------------
# DATABASES = {
#     'default': {
#         'ENGINE':   'django_tenants.postgresql_backend',
#         'NAME':     'multi_tenant_lms',
#         'USER':     'postgres',
#         'PASSWORD': 'qwerty',
#         'HOST':     'localhost',
#         'PORT':     '5432',
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'complete_multi_tenant_lms_database',
        'USER': 'complete_multi_tenant_lms_database_user',
        'PASSWORD': 'Tfxz3hVULlkbFWRWtSoN7YxRil2wWFck',
        'HOST': 'dpg-d20kmg7fte5s7391ahag-a.oregon-postgres.render.com',
        'PORT': '5432',
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = 'core.Tenant'
TENANT_DOMAIN_MODEL = 'core.Domain'

SHARED_APPS = [
    'django_tenants',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'rest_framework_simplejwt.token_blacklist',
    'core',
    'users',
    'subscriptions',
]

TENANT_APPS = [
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'courses',
    'schedule',
    'payments',
    'forum',
    'groups',
    'messaging',
    'advert',
    'compliance',
]

# -----------------------------------------------------------
# CROSS‑ORIGIN & CSRF
# -----------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'https://crm-frontend-react.vercel.app',
    'https://complete-lms-sable.vercel.app',
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'https://crm-frontend-react.vercel.app',
    'https://complete-lms-sable.vercel.app',
    'https://*.onrender.com',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-schema',
]

# -----------------------------------------------------------
# COOKIE FLAGS
# -----------------------------------------------------------
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = False  # For local development (http)
CSRF_COOKIE_SECURE = False    # For local development (http)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_PATH = '/'
CSRF_COOKIE_PATH = '/'

# -----------------------------------------------------------
# SIMPLE JWT  (Cookie‑based)
# -----------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_SECURE': False,  # Set to False for local development
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SAMESITE': 'None',
    'SIGNING_KEY': SECRET_KEY,
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
}

# -----------------------------------------------------------
# REST FRAMEWORK
# -----------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'allauth.account.auth_backends.AuthenticationBackend',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.JSONParser',
    ],
}

# -----------------------------------------------------------
# TEMPLATES
# -----------------------------------------------------------
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS':   [os.path.join(BASE_DIR, 'templates')],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

ROOT_URLCONF = 'lumina_care.urls'
WSGI_APPLICATION = 'lumina_care.wsgi.application'

# -----------------------------------------------------------
# STATIC & MEDIA
# -----------------------------------------------------------
STATIC_URL = '/static/'
MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# -----------------------------------------------------------
# LOGGING
# -----------------------------------------------------------
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{asctime} [{levelname}] {name}: {message}', 'style': '{'},
        'simple':  {'format': '[{levelname}] {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'lumina_care.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django':            {'handlers': ['file', 'console'], 'level': 'INFO', 'propagate': True},
        'core':              {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'users':             {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'talent_engine':     {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'job_application':   {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'subscriptions':     {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
    },
}

# -----------------------------------------------------------
# CRON JOBS
# -----------------------------------------------------------
CRONTAB_COMMAND_PREFIX = ''
CRONTAB_DJANGO_PROJECT_NAME = 'lumina_care'
CRONJOBS = [
    ('0 11 * * *', 'talent_engine.cron.close_expired_requisitions',
     f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
]

# -----------------------------------------------------------
# EMAIL
# -----------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'ekenehanson@gmail.com'
EMAIL_HOST_PASSWORD = 'pduw cpmw dgoq adrp'
DEFAULT_FROM_EMAIL = 'ekenehanson@gmail.com'
EMAIL_DEBUG = True

# -----------------------------------------------------------
# INTERNATIONALISATION / MISC
# -----------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Local development:

# If you need to run on plain http://localhost, change


# DEBUG = True
# SESSION_COOKIE_SECURE = False
# CSRF_COOKIE_SECURE    = False
# and optionally set SESSION/CSRF_COOKIE_SAMESITE = 'Lax'.
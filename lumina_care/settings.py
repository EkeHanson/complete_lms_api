from pathlib import Path
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(BASE_DIR / 'talent_engine'))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-!v)6(7@u983fg+8gdo1o)dr^59vvp3^ol*apr%c+$0n$#swz-1'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'complete-lms-api.onrender.com']


INSTALLED_APPS = [
    'corsheaders',
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',
    'django_crontab',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'core',
    'courses','users', 'subscriptions','schedule', 'payments', 'forum', 'groups', 'messaging', 'advert'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be first or near the top
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
# MIDDLEWARE = [
#     'corsheaders.middleware.CorsMiddleware',
#     'lumina_care.middleware.CustomTenantMiddleware',
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'allauth.account.middleware.AccountMiddleware', 
# ]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

SITE_ID = 1  # Required for django.contrib.sites

# allauth settings
ACCOUNT_LOGIN_METHODS = {'email': True}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Social providers configuration (example, configure later)
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'apple': {
        'APP': {
            'client_id': 'your.apple.client.id',
            'secret': 'your.apple.key.id',
            'key': 'your.apple.team.id',
            'certificate_key': '''-----BEGIN PRIVATE KEY-----
            YOUR_PRIVATE_KEY
            -----END PRIVATE KEY-----'''
        }
    },
    'microsoft': {
        'APP': {
            'client_id': 'your.microsoft.client.id',
            'secret': 'your.microsoft.client.secret',
            'tenant': 'common',  # For multi-tenant Azure AD
        },
        'SCOPE': ['User.Read', 'email'],
    }
}

## lumina_care/settings.py

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',  # Frontend Vite dev server
    'http://localhost:3000',  # Alternative frontend port (if used)
    'https://crm-frontend-react.vercel.app',  # Production frontend
    'https://accounts.google.com',  # For OAuth
    'https://appleid.apple.com',  # For OAuth
    'https://login.microsoftonline.com',  # For OAuth
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Add this to CORS settings
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']
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
]



# Ensure CSRF settings support cross-origin requests
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'https://crm-frontend-react.vercel.app',
    'https://2fbe-102-90-98-83.ngrok-free.app',
]



# Cookie settings for cross-origin
SESSION_COOKIE_SAMESITE = 'None' if DEBUG else 'Lax'
CSRF_COOKIE_SAMESITE = 'None' if DEBUG else 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG


CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'https://your-production-domain.com',
]


SESSION_COOKIE_SAMESITE = 'None' if DEBUG else 'Lax'
CSRF_COOKIE_SAMESITE = 'None' if DEBUG else 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

samesite = 'None' if DEBUG else 'Lax'


ROOT_URLCONF = 'lumina_care.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'lumina_care.wsgi.application'

# DATABASES = {
#     'default': {
#         'ENGINE': 'django_tenants.postgresql_backend',
#         'NAME': 'multi_tenant_lms',
#         'USER': 'postgres',
#         'PASSWORD': 'qwerty',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'lms_dbbb',
        'USER': 'lms_dbbb_user',
        'PASSWORD': 'QTcRliQDlSykdQGwla5jZ8phd9e44GeN',
        'HOST': 'dpg-d1kleuqdbo4c73a1ahk0-a.oregon-postgres.render.com',
        'PORT': '5432',
    }
}


DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = "core.Tenant"
TENANT_DOMAIN_MODEL = "core.Domain"
SHARED_APPS = [
    'django_tenants',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'rest_framework_simplejwt.token_blacklist', 
    'core','users','subscriptions',
]

TENANT_APPS = [
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'viewflow.fsm',
    'auditlog',
    'courses','schedule', 'payments', 'forum', 'groups', 'messaging', 'advert'
    'compliance',
]
AUTH_USER_MODEL = 'users.CustomUser'


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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

from datetime import timedelta
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_SECURE': True,  # Temporary change for ngrok
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SAMESITE': 'None' if DEBUG else 'Lax',
    'TOKEN_OBTAIN_SERIALIZER': 'lumina_care.views.CustomTokenSerializer',
    'SIGNING_KEY': SECRET_KEY,
}


import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

# lumina_care/settings.py
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'talent_engine'))  # For fcntl mock on Windows

# Determine log directory based on environment
if os.getenv('RENDER'):  # Render sets this environment variable
    LOG_DIR = '/tmp/logs'
else:
    LOG_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'lumina_care.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['file'],
            'level': 'ERROR',
        },
        'core': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['file'],
            'level': 'INFO',
            'propotalent_engine': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'job_application': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'subscriptions': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}}


# django-crontab configuration
CRONTAB_COMMAND_PREFIX = ''
CRONTAB_DJANGO_PROJECT_NAME = 'lumina_care'

CRONJOBS = [
    ('0 11 * * *', 'talent_engine.cron.close_expired_requisitions', f'>> {os.path.join(LOG_DIR, "lumina_care.log")} 2>&1'),
]


#payment
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Your SMTP server address
EMAIL_PORT = 587  # Your SMTP server port (587 is the default for SMTP with TLS)
EMAIL_USE_TLS = True  # Whether to use TLS (True by default)
EMAIL_HOST_USER = 'ekenehanson@gmail.com'  # Your email address
EMAIL_HOST_PASSWORD = 'pduw cpmw dgoq adrp'  # Your email password or app-specific password if using Gmail, etc.
DEFAULT_FROM_EMAIL = 'ekenehanson@gmail.com'  # The default email address to use for sending emails
EMAIL_DEBUG = True
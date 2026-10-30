import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if (BASE_DIR / '.env').exists():
    for line in (BASE_DIR / '.env').read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v)
SECRET_KEY = os.environ['SECRET_KEY']
FIELD_KEY = os.environ['FIELD_KEY']
AUDIT_KEY = os.environ['AUDIT_KEY']
PARTNER_KEYS = [os.environ[f'PARTNER_KEY_{i}'] for i in range(1, 6)]
PSP_KEY = os.environ['PSP_KEY']
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
CSRF_TRUSTED_ORIGINS = ['https://localhost:8443', 'https://127.0.0.1:8443']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'app']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'app.middleware.Guard']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('DB_NAME', 'consultas'), 'USER': os.environ.get('DB_USER', 'consultas_app'), 'PASSWORD': os.environ['DB_PASSWORD'], 'HOST': os.environ.get('DB_HOST', '127.0.0.1'), 'PORT': os.environ.get('DB_PORT', '55432'), 'CONN_MAX_AGE': 0, 'OPTIONS': {'options': '-c statement_timeout=8000 -c lock_timeout=5000'}, 'TEST': {'NAME': 'test_consultas'}}}
AUTH_USER_MODEL = 'app.User'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher']
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Strict'
SECURE_SSL_REDIRECT = os.environ.get('ALLOW_HTTP_TESTS') != '1'
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 32768
DATA_UPLOAD_MAX_NUMBER_FIELDS = 40
LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'handlers': {'console': {'class': 'logging.StreamHandler'}}, 'loggers': {'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False}, 'django.server': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False}}}

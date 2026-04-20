
from decouple import Config, Csv, RepositoryEnv
from datetime import timedelta
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

config = Config(RepositoryEnv('.env'))

ALLOWED_HOSTS = ['*'] 

SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())
AUTH_USER_MODEL = 'apihh_main.User' 

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework_simplejwt',
    'rest_framework',
    'apihh_main',
    'django_filters',
]

USE_S3_MEDIA = config('USE_S3_MEDIA', default=False, cast=bool)
if USE_S3_MEDIA:
    INSTALLED_APPS.append('storages')

SIMPLE_JWT = {
   'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),

    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),   
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,        
    'UPDATE_LAST_LOGIN': True,                      
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),  
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    
    'JTI_CLAIM': 'jti',
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated', 
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

MIDDLEWARE = [
    # Debug middleware: покажет в консоли, дошёл ли большой multipart POST до Django
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True 

ROOT_URLCONF = 'apihh_master.urls'

CORS_ALLOW_CREDENTIALS = True

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

WSGI_APPLICATION = 'apihh_master.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432', cast=int),
        'NAME': config('DB_NAME', default='kursa2'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='1'),
    }
}

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

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_ROOT = BASE_DIR / 'vacancy_videos'

if USE_S3_MEDIA:
    CLOUDRU_S3_TENANT_ID = config('CLOUDRU_S3_TENANT_ID', default='').strip()
    CLOUDRU_S3_KEY_ID = config('CLOUDRU_S3_KEY_ID', default='').strip()
    CLOUDRU_S3_KEY_SECRET = config('CLOUDRU_S3_KEY_SECRET', default='').strip()
    CLOUDRU_S3_BUCKET_NAME = config('CLOUDRU_S3_BUCKET_NAME', default='').strip()
    CLOUDRU_S3_ENDPOINT_URL = config('CLOUDRU_S3_ENDPOINT_URL', default='https://s3.cloud.ru').strip()
    CLOUDRU_S3_REGION_NAME = config('CLOUDRU_S3_REGION_NAME', default='ru-central-1').strip()
    CLOUDRU_S3_SIGNATURE_VERSION = config('CLOUDRU_S3_SIGNATURE_VERSION', default='s3v4').strip()
    CLOUDRU_S3_ADDRESSING_STYLE = config('CLOUDRU_S3_ADDRESSING_STYLE', default='path').strip()
    CLOUDRU_S3_QUERYSTRING_AUTH = config('CLOUDRU_S3_QUERYSTRING_AUTH', default=False, cast=bool)
    CLOUDRU_S3_MEDIA_PREFIX = config('CLOUDRU_S3_MEDIA_PREFIX', default='media').strip('/')
    CLOUDRU_S3_CUSTOM_DOMAIN = config('CLOUDRU_S3_CUSTOM_DOMAIN', default='').strip()

    missing_s3_settings = [
        name for name, value in {
            'CLOUDRU_S3_TENANT_ID': CLOUDRU_S3_TENANT_ID,
            'CLOUDRU_S3_KEY_ID': CLOUDRU_S3_KEY_ID,
            'CLOUDRU_S3_KEY_SECRET': CLOUDRU_S3_KEY_SECRET,
            'CLOUDRU_S3_BUCKET_NAME': CLOUDRU_S3_BUCKET_NAME,
        }.items() if not value
    ]
    if missing_s3_settings:
        raise ValueError(
            'USE_S3_MEDIA=True, but required settings are empty: '
            + ', '.join(missing_s3_settings)
        )

    AWS_ACCESS_KEY_ID = f'{CLOUDRU_S3_TENANT_ID}:{CLOUDRU_S3_KEY_ID}'
    AWS_SECRET_ACCESS_KEY = CLOUDRU_S3_KEY_SECRET
    AWS_STORAGE_BUCKET_NAME = CLOUDRU_S3_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = CLOUDRU_S3_ENDPOINT_URL
    AWS_S3_REGION_NAME = CLOUDRU_S3_REGION_NAME
    AWS_S3_SIGNATURE_VERSION = CLOUDRU_S3_SIGNATURE_VERSION
    AWS_S3_ADDRESSING_STYLE = CLOUDRU_S3_ADDRESSING_STYLE
    AWS_QUERYSTRING_AUTH = CLOUDRU_S3_QUERYSTRING_AUTH
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_LOCATION = CLOUDRU_S3_MEDIA_PREFIX
    # Игнорируем системные HTTP(S)_PROXY для S3-клиента, иначе при выключенном
    # локальном прокси (127.0.0.1:10809) загрузка падает с ProxyConnectionError.
    AWS_S3_PROXIES = {}

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

    if CLOUDRU_S3_CUSTOM_DOMAIN:
        if AWS_LOCATION:
            MEDIA_URL = f"https://{CLOUDRU_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/"
        else:
            MEDIA_URL = f"https://{CLOUDRU_S3_CUSTOM_DOMAIN}/"
    else:
        media_prefix = f"{AWS_STORAGE_BUCKET_NAME}/"
        if AWS_LOCATION:
            media_prefix = f"{media_prefix}{AWS_LOCATION}/"
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{media_prefix}"
else:
    MEDIA_URL = '/vacancy_videos/'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.mail.ru')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='')
SERVER_EMAIL = config('SERVER_EMAIL', default='')
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=30, cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)

# =====================
# Upload limits (videos)
# =====================
# По умолчанию Django ограничивает размер входящих данных в памяти (~2.5MB).
# Для multipart-видео это часто приводит к обрыву соединения на клиенте (socket closed/timeout)
# ещё во время отправки тела запроса.
# Подними лимиты под свои нужды (ниже пример на 100MB).
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024

# ⚠️ Windows + большие видео:
# Стабильнее сразу писать upload в temp-файл (не держать в памяти/не переключаться посередине).
FILE_UPLOAD_MAX_MEMORY_SIZE = 0

# Явно задаём папку для временных файлов загрузки, чтобы не зависеть от системного TEMP.
FILE_UPLOAD_TEMP_DIR = r"C:\temp\uploads"
os.makedirs(FILE_UPLOAD_TEMP_DIR, exist_ok=True)

# Форсим temp-upload handler
FILE_UPLOAD_HANDLERS = [
    'apihh_main.upload_debug.DebugUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "uploadwire": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

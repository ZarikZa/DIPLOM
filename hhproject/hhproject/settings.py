"""
Django settings for hhproject project.
"""

from datetime import timedelta
from pathlib import Path
import os

from decouple import Csv, config


BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = config(name, default=str(default))
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
        return True
    if normalized in {"0", "false", "no", "off", "", "release", "prod", "production"}:
        return False
    return default

SECRET_KEY = config("SECRET_KEY")

DEBUG = _env_bool("DEBUG", default=False)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())


INSTALLED_APPS = [
    "django_prometheus",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "home",
    "compani",
    "admin_panel",
    "apihh_main.apps.ApihhMainConfig",
    "reportlab",
]

USE_S3_MEDIA = _env_bool("USE_S3_MEDIA", default=False)
if USE_S3_MEDIA:
    INSTALLED_APPS.append("storages")


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
}


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True


MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]


ROOT_URLCONF = "hhproject.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "home.context_processors.api_user",
            ],
        },
    },
]


WSGI_APPLICATION = "hhproject.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.postgresql"),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="5432", cast=int),
        "NAME": config("DB_NAME", default="kursa2"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
    }
}

MIGRATION_MODULES = {
    "home": None,
}


AUTH_USER_MODEL = "apihh_main.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "ru"
LANGUAGES = [
    ("ru", "Русский"),
    ("en", "English"),
]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]


MEDIA_ROOT = os.path.join(BASE_DIR, "media")

if USE_S3_MEDIA:
    CLOUDRU_S3_TENANT_ID = config("CLOUDRU_S3_TENANT_ID", default="").strip()
    CLOUDRU_S3_KEY_ID = config("CLOUDRU_S3_KEY_ID", default="").strip()
    CLOUDRU_S3_KEY_SECRET = config("CLOUDRU_S3_KEY_SECRET", default="").strip()
    CLOUDRU_S3_BUCKET_NAME = config("CLOUDRU_S3_BUCKET_NAME", default="").strip()
    CLOUDRU_S3_ENDPOINT_URL = config("CLOUDRU_S3_ENDPOINT_URL", default="https://s3.cloud.ru").strip()
    CLOUDRU_S3_REGION_NAME = config("CLOUDRU_S3_REGION_NAME", default="ru-central-1").strip()
    CLOUDRU_S3_SIGNATURE_VERSION = config("CLOUDRU_S3_SIGNATURE_VERSION", default="s3v4").strip()
    CLOUDRU_S3_ADDRESSING_STYLE = config("CLOUDRU_S3_ADDRESSING_STYLE", default="path").strip()
    CLOUDRU_S3_QUERYSTRING_AUTH = _env_bool("CLOUDRU_S3_QUERYSTRING_AUTH", default=False)
    CLOUDRU_S3_MEDIA_PREFIX = config("CLOUDRU_S3_MEDIA_PREFIX", default="media").strip("/")
    CLOUDRU_S3_CUSTOM_DOMAIN = config("CLOUDRU_S3_CUSTOM_DOMAIN", default="").strip()

    missing_s3_settings = [
        name
        for name, value in {
            "CLOUDRU_S3_TENANT_ID": CLOUDRU_S3_TENANT_ID,
            "CLOUDRU_S3_KEY_ID": CLOUDRU_S3_KEY_ID,
            "CLOUDRU_S3_KEY_SECRET": CLOUDRU_S3_KEY_SECRET,
            "CLOUDRU_S3_BUCKET_NAME": CLOUDRU_S3_BUCKET_NAME,
        }.items()
        if not value
    ]
    if missing_s3_settings:
        raise ValueError(
            "USE_S3_MEDIA=True, but required settings are empty: "
            + ", ".join(missing_s3_settings)
        )

    AWS_ACCESS_KEY_ID = f"{CLOUDRU_S3_TENANT_ID}:{CLOUDRU_S3_KEY_ID}"
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
    AWS_S3_PROXIES = {}

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
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
    MEDIA_URL = "/media/"


DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
DBBACKUP_STORAGE_OPTIONS = {"location": os.path.join(MEDIA_ROOT, "backups")}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.mail.ru")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
SERVER_EMAIL = config("SERVER_EMAIL", default="")
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=30, cast=int)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", default=False)


DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
FILE_UPLOAD_TEMP_DIR = os.path.join(MEDIA_ROOT, "_tmp_uploads")
os.makedirs(FILE_UPLOAD_TEMP_DIR, exist_ok=True)
FILE_UPLOAD_HANDLERS = [
    "apihh_main.upload_debug.DebugUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
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

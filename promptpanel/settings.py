import os
import json
import logging
import secrets
from django.db.backends.sqlite3.base import DatabaseWrapper
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{name} - {levelname} - {asctime} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": os.environ.get("PROMPT_LOG_LEVEL", "WARNING"),
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": "app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
logger = logging.getLogger("app")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/
## Secret key (w/ local persistence)
def get_or_create_secret_key():
    try:
        secret_key_env = os.environ.get("PROMPT_SECRET_KEY")
        with open("/app/system.json", "r") as file:
            system = json.load(file)
        if secret_key_env and secret_key_env != "DISABLED":
            # Use environment variable if set and not disabled
            system["secret_key"] = secret_key_env
        elif not system.get("secret_key"):
            # Create a new key if not in file
            system["secret_key"] = secrets.token_urlsafe(32)
            with open("/app/system.json", "w") as file:
                json.dump(system, file)
        return system["secret_key"]
    except Exception as e:
        logger.error(e, exc_info=True)
        return secrets.token_urlsafe(32)


def get_or_create_app_id():
    try:
        with open("/app/system.json", "r") as file:
            system = json.load(file)
        if system["app_id"] != "":
            pass
        else:
            unique_id = secrets.token_urlsafe(32)
            system["app_id"] = unique_id
            with open("/app/system.json", "w") as file:
                json.dump(system, file)
        return system["app_id"]
    except Exception as e:
        logger.error(e, exc_info=True)
        return secrets.token_urlsafe(32)


APP_ID = get_or_create_app_id()
SECRET_KEY = get_or_create_secret_key()
VERSION_ID = os.environ.get("PROMPT_VERSION")
ALLOWED_HOSTS = ["*"]
DEBUG = False

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "user",
    "panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(
        ["whitenoise.middleware.WhiteNoiseMiddleware"]
        if os.environ.get("PROMPT_MODE") == "PRODUCTION"
        else []
    ),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "promptpanel.middleware.CustomErrorMiddleware",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "prompt_cache",
    }
}

X_FRAME_OPTIONS = "SAMEORIGIN"
APPEND_SLASH = True
ROOT_URLCONF = "promptpanel.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "template")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "promptpanel.context_processors.global_context",
            ],
        },
    },
]

WSGI_APPLICATION = "promptpanel.wsgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

PG_VARS = [
    "PROMPT_PG_HOST",
    "PROMPT_PG_PORT",
    "PROMPT_PG_DBNAME",
    "PROMPT_PG_USER",
    "PROMPT_PG_PASS",
]
if all(
    os.environ.get(var, "").strip().upper() != "DISABLED" for var in PG_VARS
) and all(os.environ.get(var, "").strip() for var in PG_VARS):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ.get("PROMPT_PG_HOST"),
            "PORT": os.environ.get("PROMPT_PG_PORT"),
            "NAME": os.environ.get("PROMPT_PG_DBNAME"),
            "USER": os.environ.get("PROMPT_PG_USER"),
            "PASSWORD": os.environ.get("PROMPT_PG_PASS"),
        }
    }
else:
    SQLITE_WAL = os.environ.get("PROMPT_SQLITE_WAL", "").strip().upper() == "ENABLED"
    sqlite_config = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "database/db.sqlite3",
    }
    if SQLITE_WAL:
        # Custom database wrapper to set pragmas
        class WALDatabaseWrapper(DatabaseWrapper):
            def get_new_connection(self, conn_params):
                conn = super().get_new_connection(conn_params)
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA cache_size=-64000;")
                cursor.execute("PRAGMA foreign_keys=ON;")
                return conn

        sqlite_config["ENGINE"] = "django.db.backends.sqlite3"
        sqlite_config["OPTIONS"] = {"timeout": 20}
        # Use the custom wrapper
        DatabaseWrapper = WALDatabaseWrapper
    DATABASES = {"default": sqlite_config}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Email Setup SMTP

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("PROMPT_SMTP_HOST")
EMAIL_USE_TLS = os.getenv("PROMPT_SMTP_USE_TLS", "True") == "True"
EMAIL_PORT = int(os.getenv("PROMPT_SMTP_PORT", 587))
EMAIL_HOST_USER = os.getenv("PROMPT_SMTP_USER")
EMAIL_HOST_PASSWORD = os.getenv("PROMPT_SMTP_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("PROMPT_SMTP_FROM_ADDRESS")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATICFILES_DIRS = []
# STATICFILES_DIRS = [
#     os.path.join(BASE_DIR, plugin_path) for plugin_path in glob.glob("plugins/*/static")
# ]
STATICFILES_DIRS.append(os.path.join(BASE_DIR, "static"))
STATIC_ROOT = os.path.join(BASE_DIR, "static_files")
STATIC_URL = "static/"
if os.environ.get("PROMPT_MODE") == "PRODUCTION":
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media setup
# MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("PROMPT_MAX_FILESIZE", 26214400))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("PROMPT_MAX_FILESIZE", 26214400))

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

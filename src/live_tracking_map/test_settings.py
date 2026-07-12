import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
SECRET_KEY = "test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "live_tracking_map.urls"
WSGI_APPLICATION = "live_tracking_map.wsgi.application"
ASGI_APPLICATION = "live_tracking_map.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_L10N = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "django_use_email_as_username",
    "timezone_field",
    "guardian",
    "django_countries",
    "phonenumber_field",
    "channels",
    "display.apps.DisplayConfig",
    "location_field.apps.DefaultConfig",
    "django_js_reverse",
]

AUTH_USER_MODEL = "display.MyUser"
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)
GUARDIAN_MONKEY_PATCH_USER = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": "/tmp/media", "base_url": "/media/"},
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
MEDIA_ROOT = "/tmp/media"
MEDIA_URL = "/media/"
STATIC_URL = "/static/"
STATIC_ROOT = "/tmp/static"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SUPPORT_EMAIL = "support@example.com"
SERVER_ROOT = "http://testserver"
CSRF_TRUSTED_ORIGINS = ["http://testserver"]
LOCATION_FIELD = {
    "map.provider": "openstreetmap",
    "provider.openstreetmap.max_zoom": 18,
}
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_GLOBAL_POSITIONS_KEY = "global_positions"
TRACCAR_PROTOCOL = "http"
TRACCAR_HOST = "localhost"
TRACCAR_PORT = 8082
TRACCAR_TOKEN = ""
TRACCAR_USERNAME = ""
TRACCAR_PASSWORD = ""
MBTILES_SERVER_URL = "http://localhost/"
MODE = "test"
IS_UNIT_TESTING = True
LOGGING_CONFIG = "logging.config.dictConfig"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

import os

from django.contrib import messages
from django.utils.crypto import get_random_string

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

if os.getenv("POSTIX_SECRET", ""):
    SECRET_KEY = os.getenv("POSTIX_SECRET", "")
else:
    SECRET_FILE = os.path.join(BASE_DIR, ".secret")
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r") as f:
            SECRET_KEY = f.read().strip()
    else:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        SECRET_KEY = get_random_string(50, chars)
        with open(SECRET_FILE, "w") as f:
            os.chmod(SECRET_FILE, 0o600)
            os.chown(SECRET_FILE, os.getuid(), os.getgid())
            f.write(SECRET_KEY)

DEBUG = os.getenv("POSTIX_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_filters",
    "rest_framework",
    "solo",
    "compressor",
    "postix.core",
    "postix.desk",
    "postix.api",
    "postix.backoffice",
    "postix.troubleshooter",
    "crispy_forms",
]


try:
    import django_extensions  # noqa

    INSTALLED_APPS += ("django_extensions",)
except ImportError:
    pass


MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "postix.urls"
WSGI_APPLICATION = "postix.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends." + os.getenv("POSTIX_DB_TYPE", "sqlite3"),
        "NAME": os.getenv("POSTIX_DB_NAME", "db.sqlite3"),
        "USER": os.getenv("POSTIX_DB_USER", ""),
        "PASSWORD": os.getenv("POSTIX_DB_PASS", ""),
        "HOST": os.getenv("POSTIX_DB_HOST", ""),
        "PORT": os.getenv("POSTIX_DB_PORT", ""),
        "CONN_MAX_AGE": 300
        if os.getenv("POSTIX_DB_TYPE", "sqlite3") != "sqlite3"
        else 0,
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                # list if you haven't customized them:
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "postix.troubleshooter.context.processor",
            ]
        },
    }
]

LANGUAGE_CODE = "de"
LANGUAGES = (("en", "English"), ("de", "German"))
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = [os.path.join(os.path.dirname(os.path.dirname(__file__)), "locale")]

STATIC_URL = os.getenv("POSTIX_STATIC_URL", "/static/postix/")
if os.path.exists("/srv/static"):
    # Backwards compatibility
    STATIC_ROOT = os.getenv("POSTIX_STATIC_ROOT", "/srv/static/postix/")
else:
    STATIC_ROOT = os.getenv(
        "POSTIX_STATIC_ROOT", os.path.join(os.path.dirname(__file__), "static.dist")
    )

STATICFILES_DIRS = [os.path.join(BASE_DIR, "postix", "static")]
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)
MEDIA_ROOT = os.path.join(BASE_DIR, "postix", "media")

AUTH_USER_MODEL = "core.User"

MESSAGE_TAGS = {
    messages.INFO: "info",
    messages.ERROR: "danger",
    messages.WARNING: "warning",
    50: "critical",
}

COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)

COMPRESS_CSS_FILTERS = (
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.cssmin.CSSCompressorFilter",
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "postix.api.auth.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "PAGE_SIZE": 25,
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
}

CRISPY_TEMPLATE_PACK = "bootstrap4"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django": {"handlers": ["console"], "level": "INFO"}},
}

INTERNAL_IPS = ("127.0.0.1", "::1")

try:
    import debug_toolbar  # noqa

    if DEBUG:
        INSTALLED_APPS.append("debug_toolbar.apps.DebugToolbarConfig")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        DEBUG_TOOLBAR_PATCH_SETTINGS = False
        DEBUG_TOOLBAR_CONFIG = {"JQUERY_URL": ""}
except ImportError:
    pass

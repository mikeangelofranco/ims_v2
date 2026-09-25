from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DB_CONN_MAX_AGE=(int, 60),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
ASSET_VERSION = "2026.09.15.1"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "csp",
    "django_htmx",
    "apps.accounts",
    "apps.businesses",
    "apps.common",
    "apps.dashboard",
    "apps.inventory",
    "apps.marketing",
    "apps.onboarding",
    "apps.tenancy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.tenancy.middleware.TenantResolutionMiddleware",
    "apps.tenancy.middleware.TenantAccessMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.application",
            ],
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("OPTIONS", {})["options"] = "-c timezone=Asia/Manila"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)
CSRF_FAILURE_VIEW = "apps.common.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": ("'self'",),
        "style-src": ("'self'",),
        "font-src": ("'self'",),
        "img-src": ("'self'", "data:", "blob:"),
        "connect-src": ("'self'",),
        "frame-ancestors": ("'none'",),
        "base-uri": ("'self'",),
        "form-action": ("'self'",),
    }
}

TENANT_BASE_DOMAIN = env("TENANT_BASE_DOMAIN", default="localhost")
WORKSPACE_DISPLAY_DOMAIN = env("WORKSPACE_DISPLAY_DOMAIN", default="plughubcore.com")
WORKSPACE_SESSION_GRANT_TTL_SECONDS = env.int(
    "WORKSPACE_SESSION_GRANT_TTL_SECONDS", default=60
)
TENANCY_PLATFORM_HOSTS = tuple(
    host.strip().rstrip(".").lower()
    for host in env.list("TENANCY_PLATFORM_HOSTS", default=[TENANT_BASE_DOMAIN])
)
TENANCY_EXEMPT_PATHS = (
    "/",
    "/register/",
    "/register/workspace/",
    "/register/workspace/check-slug/",
    "/register/business/",
    "/register/ready/",
    "/launch-workspace/",
    "/sign-in/",
)
TENANCY_EXEMPT_PATH_PREFIXES = ("/workspace-logo/",)
TENANCY_TENANT_PUBLIC_PATHS = ("/sign-in/", "/app/session/")
TENANCY_TENANT_PATH_PREFIXES = ("/app/", "/logout/", "/workspace-logo/")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="WARNING")},
}

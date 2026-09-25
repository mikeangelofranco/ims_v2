from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["testserver", ".localhost"]
TENANCY_PLATFORM_HOSTS = ("testserver",)
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
MIDDLEWARE = [  # noqa: F405
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

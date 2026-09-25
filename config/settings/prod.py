from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production.")
if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be configured in production.")

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = env(  # noqa: F405
    "SESSION_COOKIE_DOMAIN", default=f".{TENANT_BASE_DOMAIN}"  # noqa: F405
)
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_DOMAIN = env(  # noqa: F405
    "CSRF_COOKIE_DOMAIN", default=f".{TENANT_BASE_DOMAIN}"  # noqa: F405
)
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

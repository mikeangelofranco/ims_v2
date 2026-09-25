from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = env.list(  # noqa: F405
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", ".localhost"],
)
TENANCY_PLATFORM_HOSTS = tuple(  # noqa: F405
    host.strip().rstrip(".").lower()
    for host in env.list(  # noqa: F405
        "TENANCY_PLATFORM_HOSTS", default=["localhost", "127.0.0.1"]
    )
)
SESSION_COOKIE_SECURE = False
# Local projects share localhost and may leave parent-domain cookies behind.
# Distinct names prevent legacy sessionid/csrftoken cookies from shadowing ours.
SESSION_COOKIE_NAME = "coreflow_dev_sessionid"
CSRF_COOKIE_NAME = "coreflow_dev_csrftoken"
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)  # noqa: F405
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)  # noqa: F405
SECURE_SSL_REDIRECT = False
MIDDLEWARE = [  # noqa: F405
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

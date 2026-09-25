import hashlib
from pathlib import Path

from django.conf import settings


def asset_version():
    """Bust development caches when a generated bundle changes."""
    if not settings.DEBUG:
        return settings.ASSET_VERSION
    stamps = []
    for relative in ("static/css/app.css", "static/js/app.js"):
        try:
            stat = (Path(settings.BASE_DIR) / relative).stat()
        except FileNotFoundError:
            stamps.append("missing")
        else:
            stamps.append(f"{stat.st_mtime_ns}:{stat.st_size}")
    return hashlib.sha256("|".join(stamps).encode()).hexdigest()[:16]

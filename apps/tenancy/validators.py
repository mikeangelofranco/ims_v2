import re
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

MAX_WORKSPACE_LOGO_SIZE = 2 * 1024 * 1024
WORKSPACE_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
RESERVED_WORKSPACE_SLUGS = {"admin", "api", "app", "help", "mail", "static", "www"}


def validate_workspace_slug(value):
    if not WORKSPACE_SLUG_PATTERN.fullmatch(value):
        raise ValidationError("Use lowercase letters, numbers, and hyphens only.")
    if value in RESERVED_WORKSPACE_SLUGS:
        raise ValidationError("That workspace URL is reserved.")


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("Choose a valid timezone.") from exc


def validate_workspace_logo(upload):
    if upload.size > MAX_WORKSPACE_LOGO_SIZE:
        raise ValidationError("The workspace logo must be 2 MB or smaller.")

    extension = Path(upload.name).suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".svg"}:
        raise ValidationError("Upload a PNG, JPG, or SVG file.")

    content = upload.read(MAX_WORKSPACE_LOGO_SIZE + 1)
    upload.seek(0)
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("The selected file is not a valid PNG image.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise ValidationError("The selected file is not a valid JPG image.")
    if extension == ".svg":
        _validate_svg(content)


def _validate_svg(content):
    try:
        markup = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("The selected file is not a valid SVG image.") from exc

    normalized = markup.lower()
    forbidden = ("<!doctype", "<!entity", "<script", "foreignobject", "javascript:")
    if any(token in normalized for token in forbidden) or re.search(r"\son[a-z]+\s*=", normalized):
        raise ValidationError("The SVG contains unsafe content.")
    try:
        root = ElementTree.fromstring(markup)
    except ElementTree.ParseError as exc:
        raise ValidationError("The selected file is not a valid SVG image.") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValidationError("The selected file is not a valid SVG image.")

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.tenancy.validators import (
    validate_timezone,
    validate_workspace_logo,
    validate_workspace_slug,
)


@pytest.mark.parametrize("slug", ["Admin", "two_words", "-leading", "trailing-"])
def test_workspace_slug_rejects_invalid_or_reserved_values(slug):
    with pytest.raises(ValidationError):
        validate_workspace_slug(slug)


def test_workspace_logo_accepts_png_signature():
    logo = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n" + bytes(20))

    validate_workspace_logo(logo)

    assert logo.tell() == 0


def test_workspace_logo_rejects_disguised_executable():
    logo = SimpleUploadedFile("logo.png", b"not really a png")

    with pytest.raises(ValidationError):
        validate_workspace_logo(logo)


def test_timezone_validator_rejects_unknown_zone():
    with pytest.raises(ValidationError):
        validate_timezone("Mars/Olympus")

from pathlib import Path

from django.core.exceptions import ValidationError


def validate_product_image(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("Product images must be 5 MB or smaller.")
    extension = Path(upload.name).suffix.lower()
    content = upload.read(12)
    upload.seek(0)
    valid_png = extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n")
    valid_jpg = extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff")
    if not (valid_png or valid_jpg):
        raise ValidationError("Upload a PNG or JPG image.")

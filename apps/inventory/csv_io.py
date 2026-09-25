import csv
import io

from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import ProductForm
from .services import require_product_editor, save_product

IMPORT_FIELDS = ("name", "description", "sku", "barcode", "selling_price", "unit_cost", "is_active")


def safe_csv_cell(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@transaction.atomic
def import_products(*, file, actor):
    require_product_editor(actor)
    try:
        reader = csv.DictReader(io.StringIO(file.read().decode("utf-8-sig")), strict=True)
        if not reader.fieldnames or not {"name", "sku"}.issubset(reader.fieldnames):
            raise ValidationError("CSV must include name and sku columns.")
        count = 0
        for number, row in enumerate(reader, start=2):
            if count >= 1000:
                raise ValidationError("Import a maximum of 1,000 products at a time.")
            active = row.get("is_active", "true").strip().lower()
            if active not in ("true", "false", "1", "0"):
                raise ValidationError(f"Row {number}: is_active must be true or false.")
            form = ProductForm(
                data={
                    **{key: row.get(key, "") for key in IMPORT_FIELDS},
                    "selling_price": row.get("selling_price") or "0",
                    "unit_cost": row.get("unit_cost") or "0",
                    "is_active": active in ("true", "1"),
                }
            )
            if not form.is_valid():
                errors = "; ".join(
                    f"{key}: {', '.join(values)}" for key, values in form.errors.items()
                )
                raise ValidationError(f"Row {number}: {errors}")
            save_product(form=form, actor=actor)
            count += 1
        if not count:
            raise ValidationError("CSV contains no product rows.")
        return count
    except (UnicodeDecodeError, csv.Error, AttributeError) as exc:
        raise ValidationError("Upload a valid UTF-8 CSV file.") from exc

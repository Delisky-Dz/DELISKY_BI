"""Explicit document decisions scoped to an immutable source upload.

Unknown users remain errors. An authorized document may retain its brand totals
without asserting a truck identity; this is never a global user mapping.
"""
from datetime import date
from hashlib import sha256
import json

from apps.imports.models import DistributionBrand, ImportSourceUpload
from .batch_review import ImportBatchReviewError, _read_source_bytes
from .value_normalizers import parse_datetime_value

METADATA_KEY = "items_detail_unassigned_documents"


def invalid_decision(message):
    return ImportBatchReviewError("invalid_unassigned_document_decision", message)


def canonical(value):
    return " ".join(str(value or "").split()).upper()


def document_key(user, document, number, sale_date):
    return json.dumps([canonical(user), canonical(document), canonical(number), str(sale_date)], separators=(",", ":"))


def rules_from_upload(upload):
    entries = (upload.audit_metadata or {}).get(METADATA_KEY, []) if upload else []
    if not isinstance(entries, list):
        raise invalid_decision("Unassigned Items document decisions must be a list.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not all(entry.get(k) for k in ("source_user", "document", "document_number", "sale_date", "brand_code", "authorization")):
            raise invalid_decision("Incomplete authorized unassigned Items document decision.")
        try:
            sale_date = date.fromisoformat(entry["sale_date"])
        except (TypeError, ValueError) as exc:
            raise invalid_decision("The unassigned Items decision date is invalid.") from exc
        brand = canonical(entry["brand_code"])
        if not DistributionBrand.objects.filter(code=brand, is_active=True).exists():
            raise invalid_decision("Unassigned Items document brand must be active.")
        key = document_key(entry["source_user"], entry["document"], entry["document_number"], sale_date)
        if key in result:
            raise invalid_decision("Duplicate unassigned Items document decision.")
        result[key] = brand
    return result


def rules_for_source(source, source_system):
    file_hash = sha256(_read_source_bytes(source)).hexdigest()
    upload = ImportSourceUpload.objects.filter(file_sha256=file_hash, source_system=source_system).first()
    return rules_from_upload(upload)


def match_unassigned(rules, user, document, number, sale_datetime):
    if not rules:
        return None
    try:
        parsed = parse_datetime_value(sale_datetime)
    except ValueError:
        return None
    if parsed is None:
        return None
    return rules.get(document_key(user, document, number, parsed.date()))

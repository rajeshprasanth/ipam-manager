"""Helpers shared by web form handlers."""
from collections.abc import Mapping
from typing import Any

# Fields submitted as repeatable inputs: the browser sends one value per row,
# so these must be collected with FormData.getlist() instead of a plain lookup.
MULTI_VALUE_FIELDS = frozenset({"mac_addresses", "dns_servers"})


def clean_form(form: Any, multi_fields: frozenset[str] = MULTI_VALUE_FIELDS) -> dict[str, Any]:
    """Convert a raw form to values suitable for Pydantic validation.

    Empty strings become None so optional HTML inputs map to null columns.
    Repeatable fields keep every submitted value as a list of non-empty strings.
    """
    getlist = getattr(form, "getlist", None)
    if getlist is None:
        raw: dict[str, Any] = dict(form)
    else:
        raw = {key: value for key, value in form.items() if key not in multi_fields}
        for key in form.keys():
            if key in multi_fields:
                raw[key] = getlist(key)

    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            value = value.strip()
            cleaned[key] = value or None
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        else:
            cleaned[key] = value
    return cleaned


def model_to_form(obj: Any) -> dict[str, Any]:
    """Flatten an ORM model to a dict keyed by column name for form re-rendering."""
    data: dict[str, Any] = {}
    for column in type(obj).__table__.columns:
        data[column.name] = getattr(obj, column.name)
    return data


def list_field_values(data: Mapping[str, Any], key: str) -> list[str]:
    """Read a repeatable field for re-rendering, falling back to one blank row."""
    values = data.get(key)
    if isinstance(values, str):
        values = [values]
    values = [str(value).strip() for value in (values or []) if str(value or "").strip()]
    return values or [""]

"""Helpers shared by web form handlers."""
from typing import Any


def clean_form(form: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw form to values suitable for Pydantic validation.

    Empty strings become None so optional HTML inputs map to null columns.
    """
    cleaned: dict[str, Any] = {}
    for key, value in form.items():
        if isinstance(value, str):
            value = value.strip()
            if not value:
                value = None
        cleaned[key] = value
    return cleaned


def model_to_form(obj: Any) -> dict[str, Any]:
    """Flatten an ORM model to a dict keyed by column name for form re-rendering."""
    data: dict[str, Any] = {}
    for column in type(obj).__table__.columns:
        data[column.name] = getattr(obj, column.name)
    return data
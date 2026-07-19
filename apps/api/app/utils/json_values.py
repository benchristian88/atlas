"""Normalize Python values before assigning them to JSON/JSONB columns."""

from typing import Any

from fastapi.encoders import jsonable_encoder


def to_json_value(value: Any) -> Any:
    """Return JSON-safe primitives without pre-encoding the value as text."""

    return jsonable_encoder(value)

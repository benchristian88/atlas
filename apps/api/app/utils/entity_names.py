"""Name rules shared by canonical writes and bundled definitions."""

import re


def trim_nonempty(value: str | None) -> str:
    if value is None:
        raise ValueError("Value must not be null")
    value = value.strip()
    if not value:
        raise ValueError("Value must not be blank")
    return value


def service_slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return result[:255] or "service"

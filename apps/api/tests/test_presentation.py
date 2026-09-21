import json
from pathlib import Path
from typing import get_args
import uuid

import pytest
from pydantic import ValidationError

from app.presentation import PresentationAccent, PresentationIcon
from app.schemas import AssetCategoryCreate, AssetCategoryUpdate, NetworkCreate, NetworkUpdate


def test_web_and_api_registry_contract_cannot_drift():
    registry = json.loads((Path(__file__).parents[2] / "web/lib/presentation-registry.json").read_text())
    assert [icon["key"] for icon in registry["icons"]] == list(get_args(PresentationIcon))
    assert registry["accents"] == list(get_args(PresentationAccent))


@pytest.mark.parametrize("schema,base", [
    (AssetCategoryCreate, {"key": "custom", "name": "Custom"}),
    (AssetCategoryUpdate, {}),
    (NetworkCreate, {"customer_id": uuid.uuid4(), "name": "Custom", "network_type": "vlan"}),
    (NetworkUpdate, {}),
])
def test_presentation_valid_keys_and_strict_rejection(schema, base):
    for icon in get_args(PresentationIcon):
        assert schema(**base, icon_key=icon).icon_key == icon
    for accent in get_args(PresentationAccent):
        assert schema(**base, accent_key=accent).accent_key == accent
    for field in ("icon_key", "accent_key"):
        for invalid in (None, "", "Blue", "unknown", "#112233", "https://example.test/icon.svg", "<svg/>"):
            with pytest.raises(ValidationError):
                schema(**base, **{field: invalid})


def test_defaults_and_partial_edits_do_not_reset_other_presentation():
    category = AssetCategoryCreate(key="custom", name="Custom")
    assert (category.icon_key, category.accent_key) == ("infrastructure", "slate")
    network = NetworkCreate(customer_id=uuid.uuid4(), name="Management", network_type="vlan", vlan_id=99)
    assert (network.icon_key, network.accent_key) == ("network", "blue")
    for schema in (AssetCategoryUpdate, NetworkUpdate):
        assert schema(name="Renamed").model_dump(exclude_unset=True) == {"name": "Renamed"}
        assert schema(accent_key="rose").model_dump(exclude_unset=True) == {"accent_key": "rose"}

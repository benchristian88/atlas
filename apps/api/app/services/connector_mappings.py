"""Exact active stable-key mappings; instance-global per Connector version."""
from sqlalchemy import select

from app.models import AssetType, RelationshipType, ConnectorMapping


def declarations(manifest):
    return [("asset", row, row.get("recommended_asset_type_key")) for row in manifest.get("object_classes", []) if row["kind"] == "asset"] + [
        ("relationship", row, row.get("recommended_relationship_type_key")) for row in manifest.get("relationship_classes", [])]


def target(db, kind, key):
    model = AssetType if kind == "asset" else RelationshipType
    return db.scalar(select(model).where(model.key == key, model.active.is_(True))) if key else None


def compatible_relationship(db, manifest, declaration, record, rows):
    direction = declaration["direction"]
    if (direction == "undirected") == record.directional:
        return False
    for side in ["source", "target"]:
        allowed = getattr(record, f"allowed_{side}_asset_type_keys")
        if direction == "target_to_source":
            side = "target" if side == "source" else "source"
        keys = [rows.get(("asset", key)) for key in declaration[side + "_object_classes"]]
        if allowed and any(not row or row.target_key not in allowed for row in keys if not row or not row.ignored):
            return False
    return True


def mapping_state(db, manifest, *, auto_map=False):
    rows = {(row.kind, row.source_key): row for row in db.scalars(select(ConnectorMapping).where(
        ConnectorMapping.connector_id == manifest["id"], ConnectorMapping.connector_version == manifest["version"]))}
    result = []
    for kind, declaration, recommended in declarations(manifest):
        row = rows.get((kind, declaration["key"]))
        if row is None and auto_map:
            record = target(db, kind, recommended)
            if record is not None and (kind != "relationship" or compatible_relationship(db, manifest, declaration, record, rows)):
                row = ConnectorMapping(connector_id=manifest["id"], connector_version=manifest["version"],
                    kind=kind, source_key=declaration["key"], target_key=record.key, ignored=False,
                    asset_type_key=record.key if kind == "asset" else None,
                    relationship_type_key=record.key if kind == "relationship" else None)
                db.add(row)
                rows[(kind, declaration["key"])] = row
        record = target(db, kind, row.target_key) if row else None
        ignored = bool(row and row.ignored and not declaration["required"])
        resolved = bool(record and (kind != "relationship" or compatible_relationship(db, manifest, declaration, record, rows)))
        result.append({"kind": kind, "source_key": declaration["key"], "label": declaration["label"],
            "required": declaration["required"], "recommended_key": recommended,
            "target_key": row.target_key if row else None, "ignored": ignored,
            "resolved": resolved or ignored})
    if auto_map:
        db.flush()
    return result


def require_resolved(db, manifest, *, auto_map=False):
    rows = mapping_state(db, manifest, auto_map=auto_map)
    if any(not row["resolved"] for row in rows if row["required"]):
        raise ValueError("Resolve required global Connector mappings before activation or use")
    return rows

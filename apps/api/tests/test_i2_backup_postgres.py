"""I2 credentials through the actual existing portable backup/restore lifecycle."""
import json
import os
import secrets
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Site, DataSource, Integration, IntegrationSecret
from app.services.integration_secrets import AtlasEncryptedSecretProvider, decrypt_fields, SecretProviderError
from tests.test_backup_postgres import installations, portable_backup, restore

pytestmark = pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")), reason="requires disposable source and restore PostgreSQL databases")


def test_i2_credentials_restore_with_destination_key_without_plaintext_artifacts(installations):
    inst = installations
    values = {"token_id": "fixture_" + secrets.token_hex(8) + "@pve!probe", "token_secret": secrets.token_urlsafe(32)}
    with Session(inst["source"]) as db:
        site = db.scalar(select(Site))
        source = DataSource(customer_id=site.customer_id, site_id=site.id, name="Portable connection", source_type="connector", status="active")
        db.add(source)
        db.flush()
        row = Integration(id=uuid.uuid4(), customer_id=site.customer_id, site_id=site.id, name="Portable connection",
            plugin_id="proxmox", base_url="", username_or_token_id="", secret_reference="",
            connector_id="proxmox", connector_version="0.1.0", connector_digest="a" * 64,
            config_schema_version="1.1", data_source_id=source.id, config_json={"endpoint": "https://192.168.1.2:8006", "tls_policy": "verify"})
        db.add(row)
        db.flush()
        provider = AtlasEncryptedSecretProvider(db)
        provider.create(row, values)
        identity, source_identity = row.id, source.id
        reference = row.credential_reference
        db.commit()
    archive = portable_backup(inst)
    assert all(value.encode() not in archive.read_bytes() for value in values.values())
    assert all(value.encode() not in path.read_bytes() for path in (inst["tmp"] / "source-work").rglob("*") if path.is_file() for value in values.values())
    restore(inst, archive)
    with Session(inst["target"]) as db:
        row = db.get(Integration, identity)
        assert row.credential_reference == reference and row.data_source_id == source_identity
        record = db.get(IntegrationSecret, reference)
        assert decrypt_fields(record, bytes.fromhex(inst["target_key"]), record.encrypted_fields) == values
        with pytest.raises(SecretProviderError):
            decrypt_fields(record, bytes.fromhex(inst["source_key"]), record.encrypted_fields)
        assert all(value not in json.dumps(row.config_json) for value in values.values())

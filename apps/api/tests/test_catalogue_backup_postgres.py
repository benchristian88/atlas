"""Catalogue history survives the existing encrypted backup/restore path."""
import os
import pytest
from sqlalchemy.orm import Session
from app.models import ConnectorCatalogueRevision as Revision, ConnectorCatalogueState as State
from tests.test_backup_postgres import installations, portable_backup, restore
from tests.test_trusted_catalogue import store, RAW, DIGEST

pytestmark = pytest.mark.skipif(not (os.getenv("ATLAS_TEST_H3_SOURCE_URL") and os.getenv("ATLAS_TEST_H3_TARGET_URL")),
                               reason="requires two disposable PostgreSQL backup databases")


def test_catalogue_original_bytes_history_and_checkpoint_survive_restore(installations):
    with Session(installations["source"]) as db:
        store(db)
        original = db.get(State, 1).last_confirmed_current_at
        identities = db.get(State, 1).identity_history
    archive = portable_backup(installations)
    restore(installations, archive)
    with Session(installations["target"]) as db:
        assert db.get(Revision, 1).original_bytes == RAW
        assert db.get(State, 1).highest_digest == DIGEST
        assert db.get(State, 1).identity_history == identities
        assert db.get(State, 1).last_confirmed_current_at == original

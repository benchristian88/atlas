"""Catalogue history survives the existing encrypted backup/restore path."""
import os
import pytest
from sqlalchemy.orm import Session
from app.models import ConnectorCatalogueRevision as Revision, ConnectorCatalogueState as State
from tests.test_backup_postgres import installations, portable_backup, restore
from tests.test_trusted_catalogue import store, RAW, DIGEST
from tests.test_official_catalogue_ingestion import official_http
from tests.test_catalogue_bootstrap_authorization import bootstrap_provider
from tests.test_catalogue_publication_evidence import provider, review_document

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
        assert original is not None
        assert db.get(State, 1).last_confirmed_current_at is None
        assert db.get(State, 1).operation_id is None
        assert db.get(State, 1).lease_until is None


def test_genuine_evidence_survives_restore_and_requires_fresh_verification(installations, official_http):
    import base64
    from app.services import trusted_catalogue as consumer
    from app.services.connector_verification import GithubSigstoreVerifier
    with Session(installations["source"]) as db:
        assert consumer.refresh(db)["result"] == "accepted"
        original = db.get(Revision, 1).publication_evidence
        db.get(State, 1).next_attempt_at = consumer.source.utcnow()
        db.commit()
        # Back up a live claim too: restored ownership must be invalidated.
        assert consumer.claim(db)[1] == "claimed"
    archive = portable_backup(installations)
    restore(installations, archive)
    with Session(installations["target"]) as db:
        revision = db.get(Revision, 1)
        assert revision.publication_evidence == original
        assert db.get(State, 1).last_confirmed_current_at is None
        assert db.get(State, 1).operation_id is None
        verifier = GithubSigstoreVerifier()
        assert verifier.verify_selection(base64.b64decode(original["selection"]["source_bytes"]),
            base64.b64decode(original["pointer_bundle_base64"])).artifact_sha256 == original["pointer_sha256"]
        assert verifier.verify_catalogue(revision.original_bytes, base64.b64decode(original["catalogue_bundle_base64"]),
            subject_name="catalogue-000001.json").artifact_sha256 == DIGEST
        assert consumer.refresh(db)["result"] == "unchanged"
        assert db.get(State, 1).last_confirmed_current_at is not None

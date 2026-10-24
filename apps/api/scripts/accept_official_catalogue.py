"""Opt-in live B1.3 acceptance against an EMPTY disposable PostgreSQL database.

No executable downloads. Publication failure is explicitly NOT full acceptance.
Ordinary CI does not invoke this script.
"""
import argparse
import json
import os
from pathlib import Path
import uuid
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.authorization import Principal, ScopeGrant, get_principal
from app.database import get_db
from app.models import ConnectorCatalogueRevision, InstalledConnectorPackage, User
from app.routes import integrations
from app.services import catalogue_source as source, trusted_catalogue as consumer
from app.utils.json_values import to_json_value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-github", action="store_true", required=True)
    parser.add_argument("--disposable-database", action="store_true", required=True)
    parser.parse_args()
    url = os.environ.get("ATLAS_TEST_DATABASE_URL", "")
    parsed = make_url(url)
    if not parsed.database or not parsed.database.startswith(("atlas_b13_", "atlas_test_")):
        raise SystemExit("Use an explicitly named atlas_b13_* or atlas_test_* disposable database")
    engine = create_engine(url, hide_parameters=True)
    if inspect(engine).get_table_names():
        raise SystemExit("Refusing a nonempty database")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as db:
        user = User(email="acceptance@invalid.example", display_name="Disposable acceptance administrator",
                    password_hash="disabled-disposable-acceptance-account")
        db.add(user); db.commit(); db.refresh(user)
        principal = Principal(user, (ScopeGrant(uuid.uuid4(), uuid.uuid4(), "Master Administrator", "global",
            None, None, frozenset({"integration_runtime.view", "integration_runtime.manage"})),))
    app = FastAPI()
    app.include_router(integrations.router, prefix="/api")
    def database():
        with Session(engine) as db:
            yield db
    # Local test principal only, on an in-process disposable API, never a server.
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_principal] = lambda: principal
    captured = []
    retrieve = source.retrieve_candidate
    async def capture(progress, **kwargs):
        candidate = await retrieve(progress, **kwargs)
        captured.append(candidate)
        return candidate
    with patch.object(source, "retrieve_candidate", capture), TestClient(app) as client:
        result = client.post("/api/integration-catalogue/refresh", json={}).json()
        if result["result"] != "accepted":
            print(json.dumps(to_json_value({"live_result": result, "milestone_accepted": False}), indent=2))
            raise SystemExit(1)
        with Session(engine) as db:
            db.get(consumer.State, 1).next_attempt_at = source.utcnow()
            db.commit()
        unchanged = client.post("/api/integration-catalogue/refresh", json={}).json()
        # Preserve/report genuine partial acceptance when the anonymous provider
        # budget cannot support the required second complete verification.
        if unchanged["result"] != "unchanged":
            assert unchanged["result"] == "failed", unchanged
            assert unchanged["status"]["last_confirmed_current_at"] == result["status"]["last_confirmed_current_at"]
        api_status = client.get("/api/integration-catalogue/status").json()
        assert api_status["sequence"] == source.BOOTSTRAP_SEQUENCE
        assert api_status["content_digest"] == source.BOOTSTRAP_DIGEST
        assert all(not e["package_available"] and e["supported_actions"] == [] for e in api_status["entries"])
    engine.dispose()  # Reopen independent connections, not a Session identity map.
    with Session(engine) as db:
        persisted = consumer.status(db)
        if not captured:
            print(json.dumps(to_json_value({"live_result": result, "crypto_verified": False})))
            raise SystemExit(1)
        assert persisted["last_authenticity_verified_at"] is not None
        sequence, digest = persisted["sequence"], persisted["content_digest"]
        old_confirmation = persisted["last_confirmed_current_at"]
        state = db.get(consumer.State, 1)
        state.next_attempt_at = source.utcnow()
        db.commit()
    async def unavailable(_, **kwargs):
        raise source.SourceError("source_unavailable")
    with patch.object(source, "retrieve_candidate", unavailable), Session(engine) as db:
        failed = consumer.refresh(db)
        assert failed["result"] == "failed"
        assert consumer.status(db)["sequence"] == sequence
        assert consumer.status(db)["content_digest"] == digest
        assert consumer.status(db)["last_confirmed_current_at"] == old_confirmation
        assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 0
        revision_count = db.scalar(select(func.count()).select_from(ConnectorCatalogueRevision))
        assert revision_count == 1
    print(json.dumps(to_json_value({
        "crypto_verified": True, "policy": captured[0].authorization.policy_version,
        "approval_reference": captured[0].authorization.approval_reference,
        "selection_run": captured[0].authorization.identity.selection_run_id,
        "catalogue_source": captured[0].provenance.source_commit,
        "root_commit": captured[0].authorization.identity.root_commit,
        "historical_limitation": captured[0].authorization.historical_proof_limitation,
        "live_result": result, "unchanged_result": unchanged["result"], "api_status": api_status,
        "unchanged_error": unchanged.get("status", {}).get("last_error_code"),
        "database_reopened": True,
        "durable_revisions": revision_count, "failure_preserved_state": True,
        "last_known_good_exercised": sequence is not None,
        "packages_downloaded_or_activated": False,
        "milestone_accepted": result["result"] in {"accepted", "unchanged"},
        "complete_live_acceptance": unchanged["result"] == "unchanged",
    }), indent=2))
    engine.dispose()
    if unchanged["result"] != "unchanged":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

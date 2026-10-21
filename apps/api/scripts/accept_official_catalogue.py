"""Opt-in live B1.3 acceptance against an EMPTY disposable PostgreSQL database.

No executable downloads. Publication failure is explicitly NOT full acceptance.
Ordinary CI does not invoke this script.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import ConnectorCatalogueRevision, InstalledConnectorPackage
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
    captured = []
    retrieve = source.retrieve_candidate
    async def capture(progress):
        candidate = await retrieve(progress)
        captured.append(candidate)
        return candidate
    with patch.object(source, "retrieve_candidate", capture), Session(engine) as db:
        result = consumer.refresh(db)
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
    async def unavailable(_):
        raise source.SourceError("source_unavailable")
    with patch.object(source, "retrieve_candidate", unavailable), Session(engine) as db:
        failed = consumer.refresh(db)
        assert failed["result"] == "failed"
        assert consumer.status(db)["sequence"] == sequence
        assert consumer.status(db)["content_digest"] == digest
        assert consumer.status(db)["last_confirmed_current_at"] == old_confirmation
        assert db.scalar(select(func.count()).select_from(InstalledConnectorPackage)) == 0
        revision_count = db.scalar(select(func.count()).select_from(ConnectorCatalogueRevision))
    print(json.dumps(to_json_value({
        "crypto_verified": True, "provenance": asdict(captured[0].provenance),
        "publication": captured[0].publication, "live_result": result,
        "durable_revisions": revision_count, "failure_preserved_state": True,
        "last_known_good_exercised": sequence is not None,
        "packages_downloaded_or_activated": False,
        "milestone_accepted": result["result"] in {"accepted", "unchanged"},
    }), indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()

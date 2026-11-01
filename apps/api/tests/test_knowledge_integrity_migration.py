"""Full-schema baseline history and lossless/refused round trips on PostgreSQL.

Frozen actual baseline helpers run against the reflected 0031 model. Every
migration commits/rolls back before independent SQL state inspection.
"""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import registry

from app.database import SessionLocal

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
BASELINE = "20261021_0031"
HEAD = "20261101_0032"


@pytest.fixture
def migrated_history():
    schema = "history_" + uuid.uuid4().hex
    admin = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True,
        connect_args={"options": f"-c search_path={schema} -c lock_timeout=10000 -c statement_timeout=30000"})
    def migrate(direction, revision):
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
        # Alembic owns the transaction; failures roll back DDL AND version row.
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            getattr(command, direction)(config, revision)
    migrate("upgrade", BASELINE)
    mapper = registry()
    class LegacyAssertion:
        pass
    mapper.map_imperatively(LegacyAssertion, Table("knowledge_assertions", MetaData(), autoload_with=engine))
    path = Path(__file__).parent / "fixtures/knowledge_assertions_0031.py"
    spec = importlib.util.spec_from_file_location("baseline_assertions_" + schema, path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    helpers.KnowledgeAssertion = LegacyAssertion
    with engine.begin() as db:
        workspace = db.scalar(text("INSERT INTO workspaces(name,slug) VALUES ('History','history') RETURNING id"))
        customer = db.scalar(text("INSERT INTO customers(name,workspace_id) VALUES ('History',:workspace) RETURNING id"), {"workspace": workspace})
        site = db.scalar(text("INSERT INTO sites(name,customer_id) VALUES ('History',:customer) RETURNING id"), {"customer": customer})
        asset = db.scalar(text("INSERT INTO assets(name,asset_type,workspace_id,customer_id,site_id) VALUES ('History','virtual_machine',:workspace,:customer,:site) RETURNING id"), {"workspace": workspace, "customer": customer, "site": site})
        sources = [db.scalar(text("INSERT INTO data_sources(name,source_type,customer_id,site_id) VALUES (:name,'connector',:customer,:site) RETURNING id"), {"name": name, "customer": customer, "site": site}) for name in ("A", "B")]
    def record(db, source, value, *, predicate="hostname", external="host"):
        return helpers.record_assertion(db, customer_id=customer, site_id=site, subject_type="asset",
            subject_id=asset, subject_external_id=external, predicate=predicate, value=value, data_source_id=sources[source])[0]
    def snapshot():
        with engine.connect() as db:
            return (db.scalar(text("SELECT version_num FROM alembic_version")),
                db.execute(text("SELECT to_jsonb(a) FROM knowledge_assertions a ORDER BY id")).scalars().all(),
                db.execute(text("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema=:schema ORDER BY table_name,ordinal_position"), {"schema": schema}).all(),
                db.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=:schema ORDER BY indexname"), {"schema": schema}).all())
    state = SimpleNamespace(engine=engine, helpers=helpers, record=record, migrate=migrate,
        snapshot=snapshot, asset=asset, sources=sources, session=lambda: SessionLocal(bind=engine))
    try:
        yield state
    finally:
        mapper.dispose()
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_0032_preserves_lineage_fails_closed_and_enforces_complete_cardinality(migrated_history):
    s = migrated_history
    with s.session() as db:
        old = s.record(db, 0, "A", predicate="fixture.serial")
        new = s.record(db, 1, "B", predicate="fixture.serial")
        old.is_accepted = new.is_accepted = True
        db.commit()
        ids = old.id, new.id
    before = s.snapshot()
    with pytest.raises(RuntimeError, match="operator review"):
        s.migrate("upgrade", HEAD)
    assert s.snapshot() == before
    # Explicit synthetic operator selection, never a migration choosing a winner.
    with s.session() as db:
        s.helpers.accept_assertion(db, db.get(s.helpers.KnowledgeAssertion, ids[1]))
        db.commit()
    s.migrate("upgrade", HEAD)
    with s.engine.begin() as db:
        assert db.execute(text("SELECT superseded_by_id,acceptance_replaced_by_id,is_source_current FROM knowledge_assertions WHERE id=:id"), {"id": ids[0]}).one() == (None, ids[1], True)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text("UPDATE knowledge_assertions SET is_accepted=true WHERE id=:id"), {"id": ids[0]})
        for predicate, object_type in [("interface.eth0.ip_address", None), ("dependency", None), ("runs_on", "asset")]:
            for _ in range(2):
                db.execute(text("""INSERT INTO knowledge_assertions
                    SELECT (jsonb_populate_record(NULL::knowledge_assertions, to_jsonb(a) ||
                        jsonb_build_object('id',gen_random_uuid(),'predicate',CAST(:predicate AS text),'object_type',CAST(:object AS text)))).*
                    FROM knowledge_assertions a WHERE id=:id"""), {"id": ids[1], "predicate": predicate, "object": object_type})
    before = s.snapshot()[1]
    s.migrate("downgrade", BASELINE)
    s.migrate("upgrade", HEAD)
    assert s.snapshot()[1] == before


@pytest.mark.parametrize("scenario", ["source_only", "cross_source", "same_source_other_identity", "acceptance_chain"])
def test_0032_provable_baseline_history_round_trip(migrated_history, scenario):
    s = migrated_history
    with s.session() as db:
        old = s.record(db, 0, "A1")
        s.helpers.accept_assertion(db, old)
        db.commit()
        if scenario == "source_only":
            new = s.record(db, 0, "A2")
        else:
            new = s.record(db, 0 if scenario == "same_source_other_identity" else 1, "B", external="other" if scenario == "same_source_other_identity" else "host")
            s.helpers.accept_assertion(db, new)
        db.commit()
        if scenario == "acceptance_chain":
            last = s.record(db, 0, "C", external="other")
            s.helpers.accept_assertion(db, last)
            db.commit()
        old_id, new_id = old.id, new.id
    s.migrate("upgrade", HEAD)
    with s.engine.connect() as db:
        assert db.execute(text("SELECT superseded_by_id,acceptance_replaced_by_id FROM knowledge_assertions WHERE id=:id"), {"id": old_id}).one() == ((new_id, None) if scenario == "source_only" else (None, new_id))
    before = s.snapshot()
    s.migrate("downgrade", BASELINE)
    s.migrate("upgrade", HEAD)
    assert s.snapshot() == before


@pytest.mark.parametrize("scenario", ["stale_cross_source", "stale_same_source", "missing_decisions", "rejected", "retracted", "wrong_subject", "wrong_predicate", "reselection"])
@pytest.mark.parametrize("decision_evidence", [False, True])
def test_0032_ambiguous_or_overwritten_legacy_history_refuses_atomically(migrated_history, scenario, decision_evidence):
    s = migrated_history
    with s.session() as db:
        old = s.record(db, 0, "A1")
        if scenario != "missing_decisions":
            s.helpers.accept_assertion(db, old)
        db.commit()
        if decision_evidence:
            # Retained accepted review/Changes prove selection, but cannot
            # recover a source edge overwritten by the legacy acceptance helper.
            db.execute(text("""INSERT INTO reconciliation_items
                (customer_id,site_id,category,status,entity_type,entity_id,assertion_id,decided_at)
                VALUES (:customer,:site,'changed','accepted','asset',:asset,:claim,:at)"""),
                {"customer": old.customer_id, "site": old.site_id, "asset": old.subject_id, "claim": old.id, "at": old.first_observed_at})
            db.execute(text("""INSERT INTO knowledge_changes
                (customer_id,site_id,change_type,entity_type,entity_id,entity_name_snapshot,assertion_id,summary,occurred_at,metadata_json)
                VALUES (:customer,:site,'fact_changed','asset',:asset,'History',:claim,'Accepted synthetic history',:at,jsonb_build_object('accepted',true))"""),
                {"customer": old.customer_id, "site": old.site_id, "asset": old.subject_id, "claim": old.id, "at": old.first_observed_at})
            db.commit()
        if scenario == "reselection":
            new = s.record(db, 1, "B"); s.helpers.accept_assertion(db, new); db.commit()
            s.helpers.accept_assertion(db, old)
        else:
            new = s.record(db, 0, "A2"); db.commit()
            if scenario == "stale_cross_source":
                new = s.record(db, 1, "B")
                s.helpers.accept_assertion(db, new)
            elif scenario == "stale_same_source":
                s.helpers.accept_assertion(db, new)
            elif scenario == "rejected":
                s.helpers.reject(old)
            elif scenario == "retracted":
                from datetime import datetime, timezone
                old.is_accepted = False
                old.retracted_at = datetime.now(timezone.utc)
            elif scenario == "wrong_subject":
                new.subject_id = uuid.uuid4()
            elif scenario == "wrong_predicate":
                new.predicate = "vendor"
        db.commit()
    before = s.snapshot()
    with pytest.raises(RuntimeError, match="Operator review.*independent observation/decision evidence") as error:
        s.migrate("upgrade", HEAD)
    assert str(old.id) in str(error.value) and "Do not delete" in str(error.value)
    assert f"evidence={decision_evidence}" in str(error.value)
    assert s.snapshot() == before


@pytest.mark.parametrize("terminal", ["rejected", "retracted"])
def test_0032_terminal_assertions_without_lineage_preserve_all_history(migrated_history, terminal):
    s = migrated_history
    with s.session() as db:
        old = s.record(db, 0, "A1")
        s.helpers.reject(old)
        if terminal == "retracted":
            from datetime import datetime, timezone
            old.retracted_at = old.valid_to = datetime.now(timezone.utc)
            old.is_source_current = old.is_current = False
        db.commit()
    before = s.snapshot()[1]
    s.migrate("upgrade", HEAD)
    with s.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM knowledge_assertions")) == 1
        assert db.execute(text("SELECT superseded_by_id,acceptance_replaced_by_id FROM knowledge_assertions")).one() == (None, None)
    s.migrate("downgrade", BASELINE)
    assert s.snapshot()[1] == before


@pytest.mark.parametrize("kind", ["dual", "dual_same_target", "acceptance_stale", "unselected_source"])
def test_0032_unrepresentable_downgrade_preserves_recoverable_database(migrated_history, kind):
    s = migrated_history
    s.migrate("upgrade", HEAD)
    from app.models import KnowledgeAssertion
    from app.services.knowledge_assertions import accept_assertion, record_assertion
    with s.session() as db:
        def record(source, value):
            return record_assertion(db, customer_id=db.scalar(text("SELECT id FROM customers")),
                site_id=db.scalar(text("SELECT id FROM sites")), subject_type="asset", subject_id=s.asset,
                subject_external_id="host", predicate="hostname", value=value, data_source_id=s.sources[source])[0]
        old = record(0, "A1"); accept_assertion(db, old); db.commit()
        if kind in {"dual", "dual_same_target", "unselected_source"}:
            successor = record(0, "A2"); db.commit()
        if kind == "unselected_source":
            old.is_accepted = False
        else:
            selected = successor if kind == "dual_same_target" else record(1, "B")
            accept_assertion(db, selected)
            if kind == "acceptance_stale":
                old.is_current = old.is_source_current = False
        db.commit()
    before = s.snapshot()
    with pytest.raises(RuntimeError, match="downgrade refused"):
        s.migrate("downgrade", BASELINE)
    assert s.snapshot() == before
    with s.session() as db:
        persisted = db.get(KnowledgeAssertion, old.id)
        assert persisted.superseded_by_id == old.superseded_by_id
        assert persisted.acceptance_replaced_by_id == old.acceptance_replaced_by_id
    s.migrate("upgrade", HEAD)
    assert s.snapshot() == before

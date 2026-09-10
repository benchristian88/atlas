"""Preserve mistaken Service/BF records as non-operational tombstones.

Revision ID: 20260910_0016
Revises: 20260909_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0016"
down_revision = "20260909_0015"
branch_labels = None
depends_on = None

# All persisted direct and polymorphic operational references to these entities.
# Memberships reference dependencies/groups, whose existence already blocks Delete.
REFERENCES = {
    "service_asset_dependencies": [("service", "service_id")],
    "service_dependencies": [("service", "source_service_id"), ("service", "target_service_id")],
    "service_business_functions": [("service", "service_id"), ("business_function", "business_function_id")],
    "dependency_groups": [("service", "service_id")],
    "knowledge_assertions": [("subject_type", "subject_id"), ("object_type", "object_id")],
    "run_observed_entities": [("entity_type", "entity_id")],
    "reconciliation_items": [("entity_type", "entity_id")],
    "knowledge_gaps": [("entity_type", "entity_id")],
    "knowledge_completeness_summaries": [("entity_type", "entity_id")],
    "knowledge_changes": [("entity_type", "entity_id")],
    "audit_events": [("target_type", "target_id")],
}


def indexes(deleted: bool):
    for table in ("services", "business_functions"):
        for field in (("name", "slug") if table == "services" else ("name",)):
            for scoped in (False, True):
                suffix = f"customer_site_{field}" if scoped else f"customer_{field}_without_site"
                name = f"uq_{table}_{suffix}"
                op.drop_index(name, table_name=table)
                columns = ["customer_id"] + (["site_id"] if scoped else []) + [sa.text("lower(name)") if field == "name" else "slug"]
                predicate = "site_id IS " + ("NOT NULL" if scoped else "NULL")
                if table == "services": predicate += " AND archived_at IS NULL"
                if deleted: predicate += " AND deleted_at IS NULL"
                op.create_index(name, table, columns, unique=True, postgresql_where=sa.text(predicate))


def upgrade():
    for table in ("services", "business_functions"):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])
    indexes(True)
    # FOR SHARE conflicts with the deletion row lock, including non-key updates.
    # Writers either finish before the eligibility check or see the tombstone.
    op.execute("""
    CREATE FUNCTION atlas_guard_tombstone_reference() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE kind text; target uuid; removed timestamptz; payload jsonb;
    BEGIN
      payload := to_jsonb(NEW);
      kind := CASE WHEN TG_ARGV[0] IN ('service', 'business_function') THEN TG_ARGV[0] ELSE payload->>TG_ARGV[0] END;
      target := (payload->>TG_ARGV[1])::uuid;
      IF kind IS NULL OR kind NOT IN ('service', 'business_function') OR target IS NULL THEN RETURN NEW; END IF;
      IF kind = 'service' THEN
        SELECT deleted_at INTO removed FROM services WHERE id = target FOR SHARE;
      ELSE
        SELECT deleted_at INTO removed FROM business_functions WHERE id = target FOR SHARE;
      END IF;
      IF removed IS NOT NULL AND NOT (
        (TG_TABLE_NAME = 'audit_events' AND payload->>'event_type' = kind || '.deleted') OR
        (TG_TABLE_NAME = 'knowledge_changes' AND payload->>'change_type' = kind || '_deleted')
      ) THEN
        RAISE EXCEPTION 'Entity is unavailable' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION atlas_guard_tombstone_update() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Deleted records cannot be changed' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$;
    """)
    for table, references in REFERENCES.items():
        for index, (kind, column) in enumerate(references):
            op.execute(f"CREATE TRIGGER c26_reference_{index} BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION atlas_guard_tombstone_reference('{kind}', '{column}')")
    for table in ("services", "business_functions"):
        op.execute(f"CREATE TRIGGER c26_tombstone_update BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION atlas_guard_tombstone_update()")


def downgrade():
    # Removing tombstone state would resurrect mistakes and can reintroduce name
    # collisions. Refuse that destructive downgrade; untouched databases can roll back.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM services WHERE deleted_at IS NOT NULL)
        OR EXISTS (SELECT 1 FROM business_functions WHERE deleted_at IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot downgrade while entity tombstones exist';
      END IF;
    END $$""")
    for table, references in REFERENCES.items():
        for index, _ in enumerate(references):
            op.execute(f"DROP TRIGGER c26_reference_{index} ON {table}")
    for table in ("services", "business_functions"):
        op.execute(f"DROP TRIGGER c26_tombstone_update ON {table}")
    op.execute("DROP FUNCTION atlas_guard_tombstone_reference(); DROP FUNCTION atlas_guard_tombstone_update();")
    indexes(False)
    for table in ("services", "business_functions"):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")

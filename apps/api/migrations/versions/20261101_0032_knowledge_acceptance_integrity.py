"""Enforce the complete scalar acceptance contract and separate source lineage.

Revision ID: 20261101_0032
Revises: 20261021_0031
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20261101_0032"
down_revision = "20261021_0031"
branch_labels = None
depends_on = None

# Snapshot of predicate_cardinality, including the fail-closed unknown scalar
# default. Future cardinality changes must evolve this index in a new migration.
SINGLE_ACCEPTED = """is_accepted = true AND retracted_at IS NULL
    AND subject_id IS NOT NULL AND object_type IS NULL
    AND predicate NOT IN ('interface_ip', 'interface', 'network_membership',
                         'relationship', 'owner', 'dependency')
    AND predicate NOT LIKE 'interface.%'"""


def _legacy_edges(bind, edge_column="superseded_by_id"):
    # edge_column is an internal constant, never operator/source input.
    return bind.execute(sa.text(f"""SELECT
        a.id, a.customer_id, a.site_id, a.subject_type, a.subject_id,
        a.subject_external_id, a.predicate, a.data_source_id, a.object_type,
        a.is_current, a.is_source_current, a.is_accepted, a.retracted_at,
        a.confirmation_status, a.valid_to, a.{edge_column} AS superseded_by_id,
        b.customer_id AS next_customer, b.site_id AS next_site,
        b.subject_type AS next_type, b.subject_id AS next_subject,
        b.subject_external_id AS next_external, b.predicate AS next_predicate,
        b.data_source_id AS next_source, b.first_observed_at AS next_observed, b.object_type AS next_object_type,
        EXISTS (SELECT 1 FROM reconciliation_items r WHERE r.assertion_id = a.id
            AND r.status = 'accepted' AND r.decided_at IS NOT NULL) OR
        EXISTS (SELECT 1 FROM knowledge_changes c WHERE c.assertion_id = a.id
            AND c.metadata_json ->> 'accepted' = 'true') AS retained_acceptance
        FROM knowledge_assertions a JOIN knowledge_assertions b ON b.id = a.{edge_column}
        ORDER BY a.id""")).mappings()


def _classify(row):
    """Classify only meanings provable from the baseline helper's retained state.

    0031 source supersession cleared source-current and set valid_to; acceptance
    cleared accepted_at/by and overwrote the SAME pointer. In particular, a stale
    deselected row cannot prove whether its original source edge was overwritten,
    even if there are accepted review records. Never invent that missing edge.
    """
    context = (row["customer_id"], row["site_id"], row["subject_type"], row["predicate"])
    successor = (row["next_customer"], row["next_site"], row["next_type"], row["next_predicate"])
    same_source = (row["data_source_id"] is not None and row["data_source_id"] == row["next_source"]
                   and row["subject_external_id"] == row["next_external"])
    same_subject = (row["subject_id"] == row["next_subject"] and
                    (row["subject_id"] is not None or same_source))
    if (context != successor or not same_subject or row["object_type"] is not None or row["next_object_type"] is not None
            or row["predicate"] in {"interface_ip", "interface", "network_membership", "relationship", "owner", "dependency"}
            or row["predicate"].startswith("interface.")
            or row["id"] == row["superseded_by_id"]):
        return None
    if row["is_source_current"] and row["is_current"] and not row["is_accepted"] and row["retracted_at"] is None:
        return "acceptance"
    if (not row["is_source_current"] and not row["is_current"] and row["is_accepted"]
            and row["retracted_at"] is None and same_source
            and row["confirmation_status"] == "superseded"
            and row["valid_to"] == row["next_observed"]):
        return "source"
    return None


def _refuse(row, operation):
    raise RuntimeError(
        f"Migration 0032 {operation} refused: ambiguous or unrepresentable assertion lineage "
        f"for assertion {row['id']} -> {row['superseded_by_id']}; "
        f"retained acceptance decision evidence={bool(row['retained_acceptance'])}. "
        "Keep the current schema and a verified backup. Operator review must reconstruct "
        "an audited lineage mapping from independent observation/decision evidence in a "
        "reviewed repair migration, or restore a verified pre-loss backup. Do not delete "
        "assertions, clear historical links, or choose an accepted winner to bypass this check.")


def upgrade():
    bind = op.get_bind()
    # This is a maintenance-window migration. Freeze writers before preflight,
    # including direct assertion writes, through PostgreSQL transactional DDL.
    bind.execute(sa.text("LOCK TABLE knowledge_assertions IN ACCESS EXCLUSIVE MODE"))
    # Never choose an operator's accepted value in a migration. Abort atomically
    # before DDL if retained data violates the stronger existing domain contract.
    duplicate = bind.scalar(sa.text(f"""SELECT EXISTS (
        SELECT 1 FROM knowledge_assertions WHERE {SINGLE_ACCEPTED}
        GROUP BY subject_type, subject_id, predicate HAVING count(*) > 1)"""))
    if duplicate:
        raise RuntimeError("Conflicting accepted scalar assertions require operator review before migration 0032")
    acceptance = []
    for row in _legacy_edges(bind):
        meaning = _classify(row)
        if meaning is None:
            _refuse(row, "upgrade")
        if meaning == "acceptance":
            acceptance.append(row["id"])
    op.add_column("knowledge_assertions", sa.Column("acceptance_replaced_by_id", UUID(as_uuid=True)))
    op.create_foreign_key("fk_knowledge_assertions_acceptance_replacement",
        "knowledge_assertions", "knowledge_assertions", ["acceptance_replaced_by_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_knowledge_assertions_acceptance_replaced_by_id", "knowledge_assertions", ["acceptance_replaced_by_id"])
    if acceptance:
        bind.execute(sa.text("""UPDATE knowledge_assertions
            SET acceptance_replaced_by_id = superseded_by_id, superseded_by_id = NULL
            WHERE id = ANY(:ids)"""), {"ids": acceptance})
    op.drop_index("uq_knowledge_assertions_single_accepted", "knowledge_assertions")
    op.create_index("uq_knowledge_assertions_single_accepted", "knowledge_assertions",
        ["subject_type", "subject_id", "predicate"], unique=True, postgresql_where=sa.text(SINGLE_ACCEPTED))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text("LOCK TABLE knowledge_assertions IN ACCESS EXCLUSIVE MODE"))
    # Refuse BEFORE any DDL/data rewrite. One legacy pointer cannot represent
    # two independent meanings, even when both happen to name the same row.
    incompatible = bind.execute(sa.text("""SELECT id FROM knowledge_assertions
        WHERE acceptance_replaced_by_id IS NOT NULL AND
            (superseded_by_id IS NOT NULL OR NOT is_source_current OR NOT is_current
             OR is_accepted OR retracted_at IS NOT NULL) ORDER BY id LIMIT 1""")).scalar()
    if incompatible:
        raise RuntimeError(f"Migration 0032 downgrade refused: assertion {incompatible} has lineage "
            "the legacy single pointer cannot preserve losslessly. Keep revision 0032; "
            "use a verified matching-code backup for recovery. Do not clear historical links.")
    # Source-only rows must also survive the next upgrade's conservative
    # classifier. Refuse any state whose meaning 0031 cannot retain provably.
    for row in _legacy_edges(bind):
        if _classify(row) != "source":
            _refuse(row, "downgrade")
    for row in _legacy_edges(bind, "acceptance_replaced_by_id"):
        if _classify(row) != "acceptance":
            _refuse(row, "downgrade")
    op.drop_index("uq_knowledge_assertions_single_accepted", "knowledge_assertions")
    op.create_index("uq_knowledge_assertions_single_accepted", "knowledge_assertions",
        ["subject_type", "subject_id", "predicate"], unique=True, postgresql_where=sa.text(
            "is_accepted = true AND retracted_at IS NULL AND subject_id IS NOT NULL "
            "AND predicate IN ('name', 'hostname', 'asset_type', 'status', 'operational_state', "
            "'observation_state', 'platform', 'lifecycle_state')"))
    op.execute("""UPDATE knowledge_assertions SET superseded_by_id = acceptance_replaced_by_id
        WHERE superseded_by_id IS NULL AND acceptance_replaced_by_id IS NOT NULL""")
    op.drop_index("ix_knowledge_assertions_acceptance_replaced_by_id", "knowledge_assertions")
    op.drop_constraint("fk_knowledge_assertions_acceptance_replacement", "knowledge_assertions", type_="foreignkey")
    op.drop_column("knowledge_assertions", "acceptance_replaced_by_id")

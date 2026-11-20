"""Add retained Proxmox guest bindings and identity decision storage.

Revision ID: 20261119_0033
Revises: 20261101_0032
"""
import logging

from alembic import op
import sqlalchemy as sa


revision = "20261119_0033"
down_revision = "20261101_0032"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")
LIFETIME_KEY = "uq_entity_source_links_source_type_external"
CURRENT_KEY = "uq_entity_source_links_current_source_type_external"
HISTORICAL_KEY = "uq_entity_source_links_source_type_external_epoch"
SOURCE_KEY = ["data_source_id", "entity_type", "external_id"]
DECISIONS = "proxmox_guest_identity_decisions"


def _maintenance_lock():
    # Protect the preflight/backfill from writers. DDL will also need exclusive
    # locks. The maintenance contract requires stopping old writers and readers.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
        LOCK TABLE assets, asset_interfaces, data_sources, discovery_batch_receipts,
            discovery_runs, entity_source_links, evidence_records, integrations,
            knowledge_assertions, knowledge_changes, networks, reconciliation_items,
            run_observed_entities IN SHARE ROW EXCLUSIVE MODE
    """)


def _preflight():
    db = op.get_bind()
    # The existing validated link checks/FKs already enforce typed targets,
    # Interface ownership and target scope. Source scope is the extra join.
    wrong_scope = db.scalar(sa.text("""
        SELECT count(*) FROM entity_source_links AS link
        JOIN integrations AS integration ON integration.data_source_id = link.data_source_id
        WHERE integration.connector_id = 'proxmox'
          AND (link.customer_id, link.site_id) IS DISTINCT FROM
              (integration.customer_id, integration.site_id)
    """))
    if wrong_scope:
        raise RuntimeError(
            f"Proxmox identity migration refused: {wrong_scope} source binding(s) contradict Integration scope."
        )

    # Check all recorded context, including held evidence beyond the anchor.
    # Missing/null references can make a review incomplete. Conflicting known
    # references and duplicate open cases require operator investigation.
    wrong_context, duplicates, incomplete = db.execute(sa.text("""
        WITH cases AS (
            SELECT item.id, item.customer_id, item.site_id, item.category, item.entity_id,
                   item.candidate_external_id AS guest_key, claim.subject_external_id AS claim_key,
                   claim.customer_id AS claim_customer_id, claim.site_id AS claim_site_id,
                   claim.data_source_id AS source_id, claim.discovery_run_id AS run_id,
                   claim.evidence_record_id AS anchor_id, claim.subject_type, claim.predicate,
                   claim.value_json->'guest_observed' AS guest_observed,
                   claim.value_json->'held_evidence_ids' AS held_ids
            FROM reconciliation_items AS item
            JOIN knowledge_assertions AS claim ON claim.id = item.assertion_id
            WHERE item.status = 'open' AND item.entity_type = 'source_identity'
        ),
        held AS (
            SELECT c.id AS case_id,
                   CASE WHEN pg_input_is_valid(ref.value, 'uuid') THEN ref.value::uuid END AS evidence_id
            FROM cases AS c
            CROSS JOIN LATERAL jsonb_array_elements_text(
                CASE WHEN jsonb_typeof(c.held_ids) = 'array' THEN c.held_ids ELSE '[]'::jsonb END
            ) AS ref(value)
        ),
        evidence_refs AS (
            SELECT case_id, evidence_id FROM held
            UNION
            SELECT id, anchor_id FROM cases WHERE anchor_id IS NOT NULL
        ),
        evidence AS (
            SELECT ref.case_id, e.* FROM evidence_refs AS ref
            JOIN evidence_records AS e ON e.id = ref.evidence_id
        ),
        members AS (
            SELECT e.case_id, m.* FROM evidence AS e
            JOIN run_observed_entities AS m ON m.evidence_record_id = e.id
        ),
        run_refs AS (
            SELECT id AS case_id, run_id FROM cases WHERE run_id IS NOT NULL
            UNION SELECT case_id, discovery_run_id FROM evidence
            UNION SELECT case_id, discovery_run_id FROM members
        ),
        runs AS (
            SELECT ref.case_id, r.* FROM run_refs AS ref
            JOIN discovery_runs AS r ON r.id = ref.run_id
        ),
        receipt_rows AS (
            SELECT receipt.discovery_run_id, domain.kind, observation.value AS payload
            FROM (SELECT DISTINCT run_id FROM run_refs) AS ref
            JOIN discovery_batch_receipts AS receipt ON receipt.discovery_run_id = ref.run_id
            CROSS JOIN (VALUES ('asset', 'assets'), ('asset_interface', 'interfaces'),
                ('relationship', 'relationships')) AS domain(kind, json_key)
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(receipt.payload_json->domain.json_key) = 'array'
                     THEN receipt.payload_json->domain.json_key ELSE '[]'::jsonb END
            ) AS observation(value)
        ),
        scope_refs(case_id, customer_id, site_id, source_id) AS (
            SELECT id, customer_id, site_id, NULL::uuid FROM cases
            UNION ALL SELECT id, claim_customer_id, claim_site_id, source_id FROM cases
            UNION ALL SELECT c.id, a.customer_id, a.site_id, NULL FROM cases AS c
                      JOIN assets AS a ON a.id = c.entity_id
            UNION ALL SELECT case_id, customer_id, site_id, data_source_id FROM evidence
            UNION ALL SELECT case_id, customer_id, site_id, data_source_id FROM members
            UNION ALL SELECT case_id, customer_id, site_id, data_source_id FROM runs
            UNION ALL SELECT r.case_id, i.customer_id, i.site_id, i.data_source_id FROM runs AS r
                      JOIN integrations AS i ON i.id = r.integration_id
        ),
        source_refs AS (
            SELECT DISTINCT case_id, source_id FROM scope_refs WHERE source_id IS NOT NULL
        ),
        all_scopes AS (
            SELECT * FROM scope_refs
            UNION ALL SELECT ref.case_id, s.customer_id, s.site_id, s.id FROM source_refs AS ref
                      JOIN data_sources AS s ON s.id = ref.source_id
        ),
        conflicts AS (
            SELECT case_id FROM all_scopes GROUP BY case_id
            HAVING count(DISTINCT customer_id) > 1 OR count(DISTINCT site_id) > 1
                OR count(DISTINCT source_id) > 1
            UNION
            SELECT case_id FROM run_refs GROUP BY case_id HAVING count(*) > 1
            UNION
            SELECT c.id FROM cases AS c WHERE c.guest_key <> c.claim_key
            UNION
            SELECT c.id FROM cases AS c JOIN source_refs AS ref ON ref.case_id = c.id
            JOIN integrations AS i ON i.data_source_id = ref.source_id
            WHERE i.connector_id <> 'proxmox'
            UNION
            SELECT c.id FROM cases AS c JOIN source_refs AS ref ON ref.case_id = c.id
            JOIN entity_source_links AS link ON link.data_source_id = ref.source_id
                AND link.entity_type = 'asset' AND link.external_id = coalesce(c.guest_key, c.claim_key)
            WHERE c.entity_id <> link.entity_id
                OR c.customer_id <> link.customer_id OR c.site_id <> link.site_id
        ),
        duplicate_keys AS (
            SELECT 1 FROM cases AS c JOIN source_refs AS ref ON ref.case_id = c.id
            WHERE c.site_id IS NOT NULL AND coalesce(c.guest_key, c.claim_key) IS NOT NULL
            GROUP BY ref.source_id, c.customer_id, c.site_id, coalesce(c.guest_key, c.claim_key)
            HAVING count(*) > 1
        ),
        joinable AS (
            SELECT c.id FROM cases AS c
            JOIN integrations AS i ON (i.data_source_id, i.customer_id, i.site_id) =
                (c.source_id, c.customer_id, c.site_id) AND i.connector_id = 'proxmox'
            JOIN runs AS r ON r.case_id = c.id AND r.id = c.run_id
                AND (r.integration_id, r.data_source_id, r.customer_id, r.site_id) =
                    (i.id, c.source_id, c.customer_id, c.site_id)
            JOIN entity_source_links AS link ON (link.data_source_id, link.customer_id, link.site_id) =
                (c.source_id, c.customer_id, c.site_id) AND link.entity_type = 'asset'
                AND link.external_id = c.guest_key AND link.entity_id = c.entity_id
            WHERE c.category = 'possible_duplicate' AND c.subject_type = 'source_identity'
              AND c.predicate = 'source_key_present' AND c.claim_key = c.guest_key
              AND c.guest_key ~ '^guest/(lxc|qemu)/[1-9][0-9]{0,8}$'
              AND jsonb_typeof(c.guest_observed) = 'boolean'
              AND r.status = 'completed' AND r.completeness_status IN ('complete', 'partial')
              AND r.finalisation_hash IS NOT NULL
              AND EXISTS (SELECT 1 FROM held WHERE case_id = c.id AND evidence_id = c.anchor_id)
              AND NOT EXISTS (
                  SELECT 1 FROM evidence_refs AS ref
                  WHERE ref.case_id = c.id AND NOT EXISTS (
                      SELECT 1 FROM evidence AS e
                      JOIN members AS m ON m.case_id = e.case_id AND m.evidence_record_id = e.id
                      WHERE e.case_id = ref.case_id AND e.id = ref.evidence_id
                        AND (e.discovery_run_id, e.data_source_id, e.customer_id, e.site_id) =
                            (r.id, c.source_id, c.customer_id, c.site_id)
                        AND (m.discovery_run_id, m.data_source_id, m.customer_id, m.site_id) =
                            (r.id, c.source_id, c.customer_id, c.site_id)
                        AND (m.entity_type, m.external_id) = (e.entity_kind, e.external_id)
                        AND m.entity_id IS NULL
                        AND EXISTS (
                            SELECT 1 FROM receipt_rows AS receipt
                            WHERE (receipt.discovery_run_id, receipt.kind, receipt.payload) =
                                (e.discovery_run_id, e.entity_kind, e.payload_json)
                        )
                  )
              )
        )
        SELECT (SELECT count(*) FROM conflicts), (SELECT count(*) FROM duplicate_keys),
               (SELECT count(*) FROM cases) - (SELECT count(*) FROM joinable)
    """)).one()
    if wrong_context or duplicates:
        raise RuntimeError(
            "Proxmox identity migration refused: "
            f"{wrong_context} open case(s) have contradictory context; {duplicates} duplicate open scope/key(s)."
        )
    if incomplete:
        logger.warning(
            "Proxmox identity migration preserved %d incomplete open case(s) for fresh evidence.", incomplete
        )


def _seed_retirement_revisions():
    # Manual declarations and the absence lifecycle writer use JSON string
    # statuses. Ordinary accepted canonical field changes use {field, value}.
    # The item/Change records historical acceptance even after supersession.
    # Declared Changes can outlive a deleted assertion. A retained assertion
    # must corroborate the canonical subject and scope recorded on the Change.
    op.execute("""
        UPDATE assets AS asset SET identity_retirement_revision = 1
        WHERE asset.status = 'retired' OR (
            EXISTS (
                SELECT 1 FROM entity_source_links AS link
                JOIN integrations AS i ON (i.data_source_id, i.customer_id, i.site_id) =
                    (link.data_source_id, link.customer_id, link.site_id)
                WHERE i.connector_id = 'proxmox' AND link.entity_type = 'asset'
                  AND link.external_id ~ '^guest/(lxc|qemu)/[1-9][0-9]{0,8}$'
                  AND (link.entity_id, link.customer_id, link.site_id) =
                      (asset.id, asset.customer_id, asset.site_id)
            )
            AND EXISTS (
                SELECT 1 FROM knowledge_changes AS change
                LEFT JOIN knowledge_assertions AS status_assertion ON status_assertion.id = change.assertion_id
                  AND status_assertion.subject_type = 'asset' AND status_assertion.predicate = 'status'
                  AND status_assertion.object_type IS NULL
                  AND (status_assertion.subject_id, status_assertion.customer_id, status_assertion.site_id) =
                      (change.entity_id, change.customer_id, change.site_id)
                LEFT JOIN reconciliation_items AS item ON item.id = change.reconciliation_item_id
                  AND item.status = 'accepted' AND item.entity_type = 'asset'
                  AND (item.entity_id, item.customer_id, item.site_id) =
                      (change.entity_id, change.customer_id, change.site_id)
                WHERE change.entity_type = 'asset' AND change.predicate = 'status'
                  AND (change.entity_id, change.customer_id, change.site_id) =
                      (asset.id, asset.customer_id, asset.site_id)
                  AND (change.assertion_id IS NULL OR status_assertion.id IS NOT NULL)
                  AND (
                      (
                          (change.previous_value_json = '"retired"'::jsonb OR change.new_value_json = '"retired"'::jsonb)
                          AND change.truth_classification = 'declared'
                          AND (
                              (change.change_type = 'fact_changed'
                               AND change.metadata_json->>'origin' = 'manual_asset_edit'
                               AND change.metadata_json->'accepted' = 'true'::jsonb)
                              OR (change.change_type = 'lifecycle_changed' AND item.category = 'no_longer_observed'
                                  AND change.metadata_json->>'origin' = 'absence_review'
                                  AND change.metadata_json->>'disposition' IN
                                      ('mark_missing', 'mark_inactive', 'mark_retired', 'retire')
                                  AND EXISTS (
                                      SELECT 1 FROM knowledge_assertions AS observation
                                      WHERE observation.id = item.assertion_id
                                        AND observation.subject_type = 'asset'
                                        AND observation.predicate = 'observation_state'
                                        AND (observation.customer_id, observation.site_id) =
                                            (item.customer_id, item.site_id)
                                        AND (observation.subject_id IS NULL OR observation.subject_id = item.entity_id)
                                  ))
                          )
                      )
                      OR (
                          change.change_type = 'fact_changed' AND item.category IN ('changed', 'contradiction')
                          AND status_assertion.id = item.assertion_id
                          AND change.previous_value_json->>'field' = 'status'
                          AND change.new_value_json->>'field' = 'status'
                          AND (change.previous_value_json->'value' = '"retired"'::jsonb
                               OR change.new_value_json->'value' = '"retired"'::jsonb)
                      )
                  )
            )
        )
    """)


def _add_epoch(table, column="identity_epoch", *, nullable=False):
    op.add_column(table, sa.Column(
        column, sa.BigInteger(), nullable=nullable, server_default=None if nullable else "0",
    ))
    op.create_check_constraint(op.f(f"ck_{table}_{column}"), table, f"{column} >= 0")


def upgrade():
    _maintenance_lock()
    _preflight()
    _add_epoch("data_sources")
    _add_epoch("discovery_runs")
    _add_epoch("knowledge_assertions", nullable=True)
    _add_epoch("assets", "identity_retirement_revision")
    _seed_retirement_revisions()
    op.execute("""
        CREATE FUNCTION atlas_asset_retirement_revision() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status = 'retired' THEN
                    NEW.identity_retirement_revision := 1;
                END IF;
            ELSIF NEW.status = 'retired' AND OLD.status IS DISTINCT FROM NEW.status THEN
                NEW.identity_retirement_revision := OLD.identity_retirement_revision + 1;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER atlas_asset_retirement_revision
        BEFORE INSERT OR UPDATE OF status ON assets
        FOR EACH ROW EXECUTE FUNCTION atlas_asset_retirement_revision()
    """)

    _add_epoch("entity_source_links", "opened_epoch")
    op.add_column("entity_source_links", sa.Column("ended_epoch", sa.BigInteger()))
    op.create_check_constraint(op.f("ck_entity_source_links_ended_epoch"), "entity_source_links",
                               "ended_epoch IS NULL OR ended_epoch > opened_epoch")
    op.create_index(CURRENT_KEY, "entity_source_links", SOURCE_KEY, unique=True,
                    postgresql_where=sa.text("ended_epoch IS NULL"))
    op.create_unique_constraint(HISTORICAL_KEY, "entity_source_links", [*SOURCE_KEY, "opened_epoch"])
    op.create_index("ix_entity_source_links_current_interface_owner", "entity_source_links",
                    ["data_source_id", "customer_id", "site_id", "interface_owner_id"],
                    postgresql_where=sa.text("entity_type = 'asset_interface' AND ended_epoch IS NULL"))

    op.create_table(
        DECISIONS,
        sa.Column("reconciliation_item_id", sa.UUID(), primary_key=True),
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("identity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("old_binding_id", sa.UUID(), nullable=False),
        sa.Column("replacement_binding_id", sa.UUID()),
        sa.Column("reviewed_assertion_id", sa.UUID(), nullable=False),
        sa.Column("retirement_revision", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.UniqueConstraint("data_source_id", "identity_epoch", name="uq_proxmox_identity_decision_source_epoch"),
        sa.CheckConstraint("identity_epoch > 0", name=op.f("ck_proxmox_guest_identity_decisions_identity_epoch")),
        sa.CheckConstraint("retirement_revision >= 0", name=op.f("ck_proxmox_guest_identity_decisions_retirement_revision")),
        sa.CheckConstraint(
            "(outcome = 'reactivate' AND replacement_binding_id IS NULL) OR "
            "(outcome = 'replace' AND replacement_binding_id IS NOT NULL AND replacement_binding_id <> old_binding_id)",
            name=op.f("ck_proxmox_guest_identity_decisions_outcome"),
        ),
        sa.ForeignKeyConstraint(["reconciliation_item_id"], ["reconciliation_items.id"],
                                name="fk_proxmox_identity_decision_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"],
                                name="fk_proxmox_identity_decision_source", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["old_binding_id"], ["entity_source_links.id"],
                                name="fk_proxmox_identity_decision_old_binding", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replacement_binding_id"], ["entity_source_links.id"],
                                name="fk_proxmox_identity_decision_replacement", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_assertion_id"], ["knowledge_assertions.id"],
                                name="fk_proxmox_identity_decision_assertion", ondelete="RESTRICT"),
    )
    op.create_index("ix_proxmox_identity_decision_binding_epoch", DECISIONS,
                    ["old_binding_id", sa.text("identity_epoch DESC")])
    op.create_index("ix_proxmox_identity_decision_replacement", DECISIONS, ["replacement_binding_id"])
    op.create_index("ix_proxmox_identity_decision_assertion", DECISIONS, ["reviewed_assertion_id"])
    # MATCH SIMPLE exempts current links (NULL end). Deferred NO ACTION lets
    # the replacement writer close links before inserting the decision.
    op.create_foreign_key("fk_entity_source_links_ended_decision", "entity_source_links", DECISIONS,
                          ["data_source_id", "ended_epoch"], ["data_source_id", "identity_epoch"],
                          deferrable=True, initially="DEFERRED")
    op.drop_constraint(LIFETIME_KEY, "entity_source_links", type_="unique")


def downgrade():
    _maintenance_lock()
    op.execute(f"LOCK TABLE {DECISIONS} IN SHARE ROW EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("""
        SELECT EXISTS (SELECT 1 FROM proxmox_guest_identity_decisions)
            OR EXISTS (SELECT 1 FROM entity_source_links WHERE ended_epoch IS NOT NULL OR opened_epoch <> 0)
            OR EXISTS (SELECT 1 FROM data_sources WHERE identity_epoch <> 0)
            OR EXISTS (SELECT 1 FROM discovery_runs WHERE identity_epoch <> 0)
            OR EXISTS (SELECT 1 FROM knowledge_assertions WHERE identity_epoch <> 0)
    """)):
        raise RuntimeError(
            "Proxmox identity downgrade refused: identity decisions or binding/epoch history exist. "
            "Recover using a compatible build and verified backup."
        )

    op.create_unique_constraint(LIFETIME_KEY, "entity_source_links", SOURCE_KEY)
    op.drop_constraint("fk_entity_source_links_ended_decision", "entity_source_links", type_="foreignkey")
    op.drop_table(DECISIONS)
    op.drop_constraint(HISTORICAL_KEY, "entity_source_links", type_="unique")
    op.drop_index(CURRENT_KEY, table_name="entity_source_links")
    op.drop_index("ix_entity_source_links_current_interface_owner", table_name="entity_source_links")
    op.drop_column("entity_source_links", "ended_epoch")
    op.drop_column("entity_source_links", "opened_epoch")
    op.execute("DROP TRIGGER atlas_asset_retirement_revision ON assets")
    op.execute("DROP FUNCTION atlas_asset_retirement_revision()")
    op.drop_column("assets", "identity_retirement_revision")
    op.drop_column("knowledge_assertions", "identity_epoch")
    op.drop_column("discovery_runs", "identity_epoch")
    op.drop_column("data_sources", "identity_epoch")

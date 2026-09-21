"""Replace fixed roles with managed positions; rename relationship classification.

Revision ID: 20260921_0023
Revises: 20260921_0022
"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "20260921_0023"
down_revision = "20260921_0022"
branch_labels = None
depends_on = None

# Frozen former registry labels and order. Former ties are resolved in registry
# order so administrators can move each position independently with unique ranks.
SEEDS = [
    ("external", "External / Internet"),
    ("security_edge", "Security / edge"),
    ("routing", "Routing"),
    ("aggregation_network", "Core / aggregation network"),
    ("access_network", "Access network"),
    ("platform", "Platform / host"),
    ("infrastructure", "Infrastructure appliance"),
    ("workload", "Workload"),
    ("endpoint", "Endpoint / device"),
]


def upgrade():
    op.create_table(
        "topology_positions",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sort_order", name="uq_topology_positions_sort_order", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        sa.CheckConstraint("key <> 'automatic'", name="explicit_position"),
    )
    op.create_index("ix_topology_positions_key", "topology_positions", ["key"], unique=True)
    op.create_index("ix_topology_positions_active", "topology_positions", ["active"])
    op.add_column("asset_types", sa.Column("topology_position_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_asset_types_topology_position_id_topology_positions", "asset_types", "topology_positions", ["topology_position_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_asset_types_topology_position_id", "asset_types", ["topology_position_id"])
    db = op.get_bind()
    legacy = list(db.scalars(sa.text("SELECT DISTINCT topology_role FROM asset_types WHERE topology_role IS NOT NULL AND topology_role <> 'automatic' ORDER BY topology_role")))
    seeds = list(SEEDS)
    keys = {key for key, _ in seeds}
    names = {name for _, name in seeds}
    for key in legacy:
        if key not in keys:
            name = key
            while name in names:
                name += " (legacy)"
            names.add(name)
            seeds.append((key, name))
    for order, (key, name) in enumerate(seeds):
        position_id = uuid.uuid5(uuid.NAMESPACE_URL, f"atlas:topology-position:{key}")
        db.execute(sa.text("INSERT INTO topology_positions (id,key,name,sort_order) VALUES (:id,:key,:name,:order)"),
                   dict(id=position_id, key=key, name=name, order=order))
        db.execute(sa.text("UPDATE asset_types SET topology_position_id=:id WHERE topology_role=:key"), dict(id=position_id, key=key))
    # Customized legacy databases may have widened or removed the old check.
    for constraint in sa.inspect(db).get_check_constraints("asset_types"):
        if "topology_role" in constraint["sqltext"]:
            op.drop_constraint(op.f(constraint["name"]), "asset_types", type_="check")
    op.drop_column("asset_types", "topology_role")
    op.drop_constraint("ck_relationship_types_topology_layer", "relationship_types", type_="check")
    op.alter_column("relationship_types", "topology_layer", new_column_name="topology_class")
    op.create_check_constraint("ck_relationship_types_topology_class", "relationship_types",
                               "topology_class IN ('platform', 'physical_network', 'data_resilience', 'logical_operational', 'other')")


def downgrade():
    db = op.get_bind()
    # Never truncate a custom key to fit the former varchar(32). Refuse the
    # transaction before changing anything; the operator can explicitly reassign.
    if db.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM asset_types a JOIN topology_positions p ON p.id=a.topology_position_id WHERE length(p.key)>32)")):
        raise RuntimeError("Cannot downgrade: an assigned topology position key exceeds the former 32-character limit; reassign it explicitly first")
    op.add_column("asset_types", sa.Column("topology_role", sa.String(32), nullable=False, server_default="automatic"))
    db.execute(sa.text("UPDATE asset_types a SET topology_role=p.key FROM topology_positions p WHERE p.id=a.topology_position_id"))
    # Preserve custom keys as well as built-ins in the rollback schema. The old
    # bounded check is widened only to keys actually used at downgrade time.
    keys = [key for key, _ in SEEDS] + ["automatic"]
    keys += list(db.scalars(sa.text("SELECT DISTINCT topology_role FROM asset_types ORDER BY topology_role")))
    literals = ", ".join("'" + key.replace("'", "''") + "'" for key in sorted(set(keys)))
    op.create_check_constraint("ck_asset_types_topology_role", "asset_types", f"topology_role IN ({literals})")
    op.drop_index("ix_asset_types_topology_position_id", table_name="asset_types")
    op.drop_constraint("fk_asset_types_topology_position_id_topology_positions", "asset_types", type_="foreignkey")
    op.drop_column("asset_types", "topology_position_id")
    op.drop_table("topology_positions")
    op.drop_constraint("ck_relationship_types_topology_class", "relationship_types", type_="check")
    op.alter_column("relationship_types", "topology_class", new_column_name="topology_layer")
    op.create_check_constraint("ck_relationship_types_topology_layer", "relationship_types",
                               "topology_layer IN ('platform', 'physical_network', 'data_resilience', 'logical_operational', 'other')")

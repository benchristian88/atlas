"""Managed relationship topology presentation layers.

Revision ID: 20260921_0021
Revises: 20260921_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0021"
down_revision = "20260921_0020"
branch_labels = None
depends_on = None

# Exact seeded keys only; never classify custom rows from names or key similarity.
BUILTIN_LAYERS = {
    "platform": ["contains", "hosts", "hosted_on", "runs_on", "runs", "member_of"],
    "physical_network": [
        "connects_to", "connected_to", "belongs_to_network", "uplinks_to", "connected_via",
    ],
    "data_resilience": [
        "uses_storage", "backs_up_to", "backed_up_by", "replicates_to", "syncs_to",
    ],
    "logical_operational": [
        "protects", "protected_by", "depends_on", "monitors", "proxies", "authenticates",
        "exposes", "served_by", "provides_service_to", "managed_by",
    ],
    "other": ["related_to", "routes"],
}



def upgrade():
    op.add_column("relationship_types", sa.Column("topology_layer", sa.String(32), nullable=False, server_default="other"))
    op.create_check_constraint("ck_relationship_types_topology_layer", "relationship_types",
                               "topology_layer IN ('platform', 'physical_network', 'data_resilience', 'logical_operational', 'other')")
    for layer, keys in BUILTIN_LAYERS.items():
        for key in keys:
            op.get_bind().execute(sa.text(
                "UPDATE relationship_types SET topology_layer=:layer WHERE key=:key AND system_defined IS TRUE"
            ), {"layer": layer, "key": key})


def downgrade():
    op.drop_constraint("ck_relationship_types_topology_layer", "relationship_types", type_="check")
    op.drop_column("relationship_types", "topology_layer")

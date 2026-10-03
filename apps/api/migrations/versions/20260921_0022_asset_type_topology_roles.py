"""Managed Asset Type topology presentation roles.

Revision ID: 20260921_0022
Revises: 20260921_0021
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0022"
down_revision = "20260921_0021"
branch_labels = None
depends_on = None

# One-time defaults for exact built-in keys. Custom and unknown types stay automatic.
BUILTIN_ROLES = {'security_edge': ['firewall'],
 'routing': ['router'],
 'access_network': ['switch', 'network_switch', 'access_point', 'network_bridge'],
 'platform': ['proxmox_host',
              'hypervisor_node',
              'node',
              'server',
              'physical_server',
              'docker_host'],
 'infrastructure': ['nas', 'storage_pool', 'backup_target'],
 'workload': ['virtual_machine',
              'container',
              'lxc_container',
              'docker_container',
              'application',
              'proxy',
              'database',
              'backup_job'],
 'automatic': ['unknown', 'network', 'vlan', 'proxmox_cluster', 'service']}


def upgrade():
    op.add_column("asset_types", sa.Column("topology_role", sa.String(32), nullable=False, server_default="automatic"))
    op.create_check_constraint("ck_asset_types_topology_role", "asset_types",
                               "topology_role IN ('external', 'security_edge', 'routing', 'aggregation_network', 'access_network', 'platform', 'infrastructure', 'workload', 'endpoint', 'automatic')")
    for role, keys in BUILTIN_ROLES.items():
        for key in keys:
            op.get_bind().execute(sa.text(
                "UPDATE asset_types SET topology_role=:role WHERE key=:key AND system_defined IS TRUE"
            ), {"role": role, "key": key})


def downgrade():
    op.drop_constraint("ck_asset_types_topology_role", "asset_types", type_="check")
    op.drop_column("asset_types", "topology_role")

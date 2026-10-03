"""First-run installation state and database-backed session lifetime.

Revision ID: 20261004_0025
Revises: 20261004_0024
"""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0025"
down_revision = "20261004_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "installation_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("initialized_at", sa.DateTime(timezone=True)),
        sa.Column("setup_code_hash", sa.String(255)),
        sa.Column("setup_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("setup_generation >= 0 AND failed_attempts >= 0", name="nonnegative"),
        sa.CheckConstraint("initialized_at IS NULL OR setup_code_hash IS NULL", name="no_initialized_verifier"),
    )
    # Any existing account closes setup, including disabled accounts. Never
    # reactivate first-run merely because accounts are later removed/disabled.
    op.execute("""INSERT INTO installation_state (id, initialized_at)
        SELECT 1, CASE WHEN EXISTS (SELECT 1 FROM users) THEN now() ELSE NULL END""")
    op.execute("""INSERT INTO system_settings (key, value, description, sensitive)
        VALUES ('auth.session_minutes', '480'::jsonb,
        'Session lifetime in minutes (1–10080). Changes apply to newly issued sessions.', false)
        ON CONFLICT (key) DO NOTHING""")


def downgrade():
    # Downgrade removes first-run protection; use matched code/schema releases.
    op.execute("DELETE FROM system_settings WHERE key = 'auth.session_minutes'")
    op.drop_table("installation_state")

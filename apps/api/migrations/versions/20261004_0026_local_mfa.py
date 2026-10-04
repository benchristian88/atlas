"""Encrypted local TOTP, one-time recovery verifiers and scoped login attempts.

Revision ID: 20261004_0026
Revises: 20261004_0025
Existing users remain unenrolled; passwords and RBAC are preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261004_0026"
down_revision = "20261004_0025"
branch_labels = None
depends_on = None


def upgrade():
    # The pre-H2 boolean was a reserved placeholder, never an enrolled factor.
    op.execute("UPDATE users SET mfa_enabled = false WHERE mfa_enabled")
    op.create_table("user_mfa",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("encryption_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("secret_ciphertext", sa.LargeBinary()), sa.Column("secret_nonce", sa.LargeBinary()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("last_totp_step", sa.BigInteger()),
        sa.Column("pending_ciphertext", sa.LargeBinary()), sa.Column("pending_nonce", sa.LargeBinary()),
        sa.Column("pending_id", postgresql.UUID(as_uuid=True)), sa.Column("pending_expires_at", sa.DateTime(timezone=True)),
        sa.Column("pending_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("encryption_version = 1", name="encryption_version"),
        sa.CheckConstraint("(secret_ciphertext IS NULL) = (secret_nonce IS NULL)", name="active_pair"),
        sa.CheckConstraint("(pending_ciphertext IS NULL AND pending_nonce IS NULL AND pending_id IS NULL AND pending_expires_at IS NULL) OR (pending_ciphertext IS NOT NULL AND pending_nonce IS NOT NULL AND pending_id IS NOT NULL AND pending_expires_at IS NOT NULL)", name="pending_complete"),
    )
    op.create_table("mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_mfa.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("verifier", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"])
    op.create_table("mfa_challenges",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    # Explicit rollback retires authentication material only; never run on an
    # active installation without coordinating application version and access.
    op.execute("UPDATE users SET mfa_enabled = false, session_version = session_version + 1 WHERE mfa_enabled")
    op.drop_table("mfa_challenges")
    op.drop_table("mfa_recovery_codes")
    op.drop_table("user_mfa")

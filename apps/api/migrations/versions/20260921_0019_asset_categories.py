"""Managed Asset Categories; preserve the legacy column as an upgrade snapshot.

Revision ID: 20260921_0019
Revises: 20260912_0018
"""
import re
import uuid

from alembic import op
import sqlalchemy as sa

revision = "20260921_0019"
down_revision = "20260912_0018"
branch_labels = None
depends_on = None

UNCATEGORIZED_ID = uuid.UUID("cbb23449-f856-5a92-a031-02c83946b579")
NAMESPACE = uuid.UUID("321cd02c-1b96-43ec-a934-6d193fd85bcb")


def category_rows(values):
    """Exact legacy values remain distinct, even after slug collisions."""
    used = {"uncategorized"}
    rows = []
    for value in sorted({v for v in values if v and v.strip()}):
        if value == "Uncategorized":
            rows.append((value, UNCATEGORIZED_ID, "uncategorized"))
            continue
        base = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80] or "category"
        if not base[0].isalpha():
            base = "category_" + base
        key = base
        suffix = 2
        while key in used:
            key = f"{base}_{suffix}"
            suffix += 1
        used.add(key)
        rows.append((value, uuid.uuid5(NAMESPACE, value), key))
    return rows


def upgrade():
    op.create_table(
        "asset_categories",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_in_topology", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("key <> 'uncategorized' OR active", name="uncategorized_active"),
    )
    for field in ("key", "sort_order", "active"):
        op.create_index(f"ix_asset_categories_{field}", "asset_categories", [field], unique=field == "key")
    table = sa.table("asset_categories", sa.column("id", sa.Uuid()), sa.column("key"), sa.column("name"), sa.column("show_in_topology", sa.Boolean()))
    op.execute(table.insert().values(id=UNCATEGORIZED_ID, key="uncategorized", name="Uncategorized", show_in_topology=False))
    op.add_column("asset_types", sa.Column("category_id", sa.Uuid(), nullable=False, server_default=str(UNCATEGORIZED_ID)))
    connection = op.get_bind()
    values = connection.execute(sa.text("SELECT DISTINCT category FROM asset_types")).scalars()
    for name, category_id, key in category_rows(values):
        if category_id != UNCATEGORIZED_ID:
            connection.execute(table.insert().values(id=category_id, key=key, name=name, show_in_topology=True))
        connection.execute(sa.text("UPDATE asset_types SET category_id = :id WHERE category = :name"), {"id": category_id, "name": name})
    op.create_foreign_key("fk_asset_types_category_id_asset_categories", "asset_types", "asset_categories", ["category_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_asset_types_category_id", "asset_types", ["category_id"])
    # The fallback must survive direct reference-data maintenance as well as APIs.
    op.execute("""CREATE FUNCTION protect_uncategorized_category() RETURNS trigger AS $$
    BEGIN
        IF OLD.key = 'uncategorized' AND (TG_OP = 'DELETE' OR NEW.key <> OLD.key OR NEW.name <> 'Uncategorized' OR NOT NEW.active) THEN
            RAISE EXCEPTION 'Uncategorized is protected';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("CREATE TRIGGER protect_uncategorized BEFORE DELETE OR UPDATE ON asset_categories FOR EACH ROW EXECUTE FUNCTION protect_uncategorized_category()")


def downgrade():
    # Preserve current managed display values for older applications.
    op.execute("UPDATE asset_types SET category = c.name FROM asset_categories c WHERE c.id = asset_types.category_id")
    op.drop_column("asset_types", "category_id")
    op.drop_table("asset_categories")
    op.execute("DROP FUNCTION protect_uncategorized_category()")

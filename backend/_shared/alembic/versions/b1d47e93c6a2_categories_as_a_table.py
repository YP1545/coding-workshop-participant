"""Replace the incident_category enum with a categories table.

Part of: backend / migrations.

Why this exists: the category list was a PostgreSQL enum type, which made
adding a category a code change plus a migration plus a redeploy. A facility
admin should be able to add one by inserting a row.

What is kept: the column still holds the slug ("hvac"), so the API contract does
not change and serialising an incident still needs no join. What changes is what
guards it — a foreign key to incident_categories instead of an enum type. Just
as strict, but the allowed values are now data.

Revision ID: b1d47e93c6a2
Revises: 8f3c21a4d5e7
"""

from alembic import op
import sqlalchemy as sa


revision = "b1d47e93c6a2"
down_revision = "8f3c21a4d5e7"
branch_labels = None
depends_on = None

# The nine values the enum used to hold, with the names people read. Ordered in
# tens so a new category can be slotted between two existing ones without
# renumbering the rest.
SEED_CATEGORIES = [
    ("hvac", "Heating, ventilation and air conditioning", 10),
    ("electrical", "Electrical", 20),
    ("plumbing", "Plumbing", 30),
    ("furniture", "Furniture", 40),
    ("network", "Network", 50),
    ("hardware", "Hardware", 60),
    ("software", "Software", 70),
    ("access_security", "Access and security", 80),
    ("other", "Other", 90),
]


def upgrade() -> None:
    categories = op.create_table(
        "incident_categories",
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("slug", name="pk_incident_categories"),
    )

    op.bulk_insert(categories, [
        {"slug": slug, "name": name, "sort_order": order}
        for slug, name, order in SEED_CATEGORIES
    ])

    # The column already holds exactly these slugs — it was an enum over the
    # same values — so the cast cannot lose anything and no backfill is needed.
    op.execute("ALTER TABLE incidents ALTER COLUMN category DROP DEFAULT")
    op.execute("ALTER TABLE incidents ALTER COLUMN category TYPE TEXT USING category::text")
    op.execute("ALTER TABLE incidents ALTER COLUMN category SET DEFAULT 'other'")

    op.create_foreign_key(
        "fk_incidents_category", "incidents", "incident_categories",
        ["category"], ["slug"], ondelete="RESTRICT",
    )

    # Nothing references the enum type now, and leaving it behind would make a
    # later re-run of this migration fail with "type already exists".
    op.execute("DROP TYPE IF EXISTS incident_category")


def downgrade() -> None:
    op.drop_constraint("fk_incidents_category", "incidents", type_="foreignkey")

    # Rebuild the enum from the rows, so a category added since this migration
    # ran is carried back rather than dropped — and if one is in use the cast
    # below fails loudly instead of silently losing incidents.
    op.execute(
        """
        DO $$
        DECLARE values_list text;
        BEGIN
            SELECT string_agg(quote_literal(slug), ', ' ORDER BY sort_order)
            INTO values_list FROM incident_categories;
            EXECUTE 'CREATE TYPE incident_category AS ENUM (' || values_list || ')';
        END $$;
        """
    )

    op.execute("ALTER TABLE incidents ALTER COLUMN category DROP DEFAULT")
    op.execute(
        "ALTER TABLE incidents ALTER COLUMN category "
        "TYPE incident_category USING category::incident_category"
    )
    op.execute("ALTER TABLE incidents ALTER COLUMN category SET DEFAULT 'other'")

    op.drop_table("incident_categories")

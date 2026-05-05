"""Add google_event_id to appointments table.

Revision ID: f7a1b2c3d4e5
Revises: 124ea28e0e49
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f7a1b2c3d4e5"
down_revision = "124ea28e0e49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("google_event_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_appointments_google_event_id",
        "appointments",
        ["google_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_appointments_google_event_id",
        table_name="appointments",
    )
    op.drop_column("appointments", "google_event_id")

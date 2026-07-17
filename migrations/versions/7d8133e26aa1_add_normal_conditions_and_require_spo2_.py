from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7d8133e26aa1"
down_revision: Union[str, Sequence[str], None] = "0f4ec5017182"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enums must be updated explicitly.
    op.execute("ALTER TYPE condition_key " "ADD VALUE IF NOT EXISTS 'HR_NORMAL'")

    op.execute("ALTER TYPE condition_key " "ADD VALUE IF NOT EXISTS 'SPO2_NORMAL'")

    # Populate existing patients before making the field required.
    op.execute("""
        UPDATE elderly_patients
        SET usual_spo2_min = 95
        WHERE usual_spo2_min IS NULL
        """)

    op.alter_column(
        "elderly_patients",
        "usual_spo2_min",
        existing_type=sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("95"),
    )


def downgrade() -> None:
    op.alter_column(
        "elderly_patients",
        "usual_spo2_min",
        existing_type=sa.SmallInteger(),
        nullable=True,
        server_default=None,
    )

    # PostgreSQL cannot safely remove individual enum values using
    # ALTER TYPE. HR_NORMAL and SPO2_NORMAL are therefore retained.

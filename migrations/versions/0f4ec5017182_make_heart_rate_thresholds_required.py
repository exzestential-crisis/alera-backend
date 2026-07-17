"""make heart rate thresholds required

Revision ID: 0f4ec5017182
Revises: 92c3a7fee6de
Create Date: 2026-07-17 12:20:48.535186

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0f4ec5017182"
down_revision: Union[str, Sequence[str], None] = "92c3a7fee6de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make heart-rate thresholds required."""

    op.execute("""
        UPDATE elderly_patients
        SET normal_hr_min = 60
        WHERE normal_hr_min IS NULL
        """)

    op.execute("""
        UPDATE elderly_patients
        SET normal_hr_max = 100
        WHERE normal_hr_max IS NULL
        """)

    op.alter_column(
        "elderly_patients",
        "normal_hr_min",
        existing_type=sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("60"),
    )

    op.alter_column(
        "elderly_patients",
        "normal_hr_max",
        existing_type=sa.SmallInteger(),
        nullable=False,
        server_default=sa.text("100"),
    )


def downgrade() -> None:
    """Allow nullable heart-rate thresholds again."""

    op.alter_column(
        "elderly_patients",
        "normal_hr_max",
        existing_type=sa.SmallInteger(),
        nullable=True,
        server_default=None,
    )

    op.alter_column(
        "elderly_patients",
        "normal_hr_min",
        existing_type=sa.SmallInteger(),
        nullable=True,
        server_default=None,
    )

"""add patient threshold constraints

Revision ID: b86c2c0d44f1
Revises: 7d8133e26aa1
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b86c2c0d44f1"
down_revision: Union[str, Sequence[str], None] = "7d8133e26aa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINTS = {
    "ck_patient_hr_min_positive": "normal_hr_min > 0",
    "ck_patient_hr_max_positive": "normal_hr_max > 0",
    "ck_patient_hr_range_order": "normal_hr_min <= normal_hr_max",
    "ck_patient_spo2_min_range": "usual_spo2_min BETWEEN 0 AND 100",
    "ck_patient_spo2_max_range": (
        "usual_spo2_max IS NULL OR usual_spo2_max BETWEEN 0 AND 100"
    ),
    "ck_patient_spo2_range_order": (
        "usual_spo2_max IS NULL OR usual_spo2_min <= usual_spo2_max"
    ),
}


def upgrade() -> None:
    for name, condition in CONSTRAINTS.items():
        op.create_check_constraint(name, "elderly_patients", condition)


def downgrade() -> None:
    for name in reversed(CONSTRAINTS):
        op.drop_constraint(name, "elderly_patients", type_="check")

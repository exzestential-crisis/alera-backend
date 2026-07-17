import pytest
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


def test_database_rejects_invalid_threshold_if_application_hook_is_bypassed(
    db_session,
    patient,
):
    # The model hook is tested separately. This update exercises the database
    # check constraint directly rather than duplicating application behavior.
    with pytest.raises(IntegrityError):
        db_session.connection().exec_driver_sql(
            "UPDATE elderly_patients SET normal_hr_min = 0 WHERE patient_id = %s",
            (patient.patient_id,),
        )
    db_session.rollback()

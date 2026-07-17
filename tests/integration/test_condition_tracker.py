from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.condition_trackers.model import ConditionTracker
from app.event_evaluations.model import ConditionKey
from app.health_events.model import MetricType, ValidationStatus
from app.health_events.schema import HealthEventCreate
from app.health_events.service import create_health_event

pytestmark = pytest.mark.integration


def ingest(db, patient, metric_type, value, when):
    return create_health_event(
        db,
        HealthEventCreate(
            patient_id=patient.patient_id,
            metric_type=metric_type,
            numeric_value=value,
            recorded_at=when,
            validation_status=ValidationStatus.VALID_REALTIME,
        ),
    )


def test_normal_event_resolves_all_metric_conditions(db_session, patient):
    now = datetime(2026, 7, 17, 5, tzinfo=timezone.utc)
    ingest(db_session, patient, MetricType.HEART_RATE, "110", now)
    ingest(db_session, patient, MetricType.HEART_RATE, "45", now + timedelta(seconds=1))
    ingest(db_session, patient, MetricType.HEART_RATE, "78", now + timedelta(seconds=2))
    trackers = db_session.scalars(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == patient.patient_id
        )
    ).all()
    assert {item.condition_key for item in trackers} == {
        ConditionKey.HR_HIGH,
        ConditionKey.HR_LOW,
    }
    assert all(item.active is False for item in trackers)


def test_only_one_tracker_exists_per_patient_condition(db_session, patient):
    now = datetime(2026, 7, 17, 5, tzinfo=timezone.utc)
    ingest(db_session, patient, MetricType.HEART_RATE, "110", now)
    ingest(db_session, patient, MetricType.HEART_RATE, "120", now + timedelta(seconds=1))
    count = db_session.scalar(
        select(func.count(ConditionTracker.condition_tracker_id)).where(
            ConditionTracker.patient_id == patient.patient_id,
            ConditionTracker.condition_key == ConditionKey.HR_HIGH,
        )
    )
    assert count == 1

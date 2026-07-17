from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.condition_trackers.model import ConditionTracker
from app.event_evaluations.model import ConditionKey
from app.health_events.model import MetricType, ValidationStatus
from app.health_events.schema import HealthEventCreate
from app.health_events.service import create_health_event

pytestmark = pytest.mark.integration
BASE_TIME = datetime(2026, 7, 17, 5, tzinfo=timezone.utc)


def concurrent_ingest(engine, patient_id, specifications):
    barrier = Barrier(len(specifications))
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def worker(specification):
        session = factory()
        try:
            event = HealthEventCreate(
                patient_id=patient_id,
                external_event_id=f"concurrent-{uuid4()}",
                validation_status=ValidationStatus.VALID_REALTIME,
                **specification,
            )
            barrier.wait()
            return create_health_event(session, event).event_id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=len(specifications)) as executor:
        return list(executor.map(worker, specifications))


def test_two_simultaneous_first_hr_high_events_create_one_tracker(
    integration_engine,
    db_session,
    patient,
):
    event_ids = concurrent_ingest(
        integration_engine,
        patient.patient_id,
        [
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "110",
                "recorded_at": BASE_TIME,
            },
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "120",
                "recorded_at": BASE_TIME + timedelta(seconds=1),
            },
        ],
    )
    db_session.expire_all()
    trackers = db_session.scalars(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == patient.patient_id,
            ConditionTracker.condition_key == ConditionKey.HR_HIGH,
        )
    ).all()
    assert len(event_ids) == 2
    assert len(trackers) == 1
    assert trackers[0].last_seen_at == BASE_TIME + timedelta(seconds=1)


def test_simultaneous_high_and_low_use_independent_trackers(
    integration_engine,
    db_session,
    patient,
):
    concurrent_ingest(
        integration_engine,
        patient.patient_id,
        [
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "110",
                "recorded_at": BASE_TIME,
            },
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "45",
                "recorded_at": BASE_TIME,
            },
        ],
    )
    db_session.expire_all()
    trackers = db_session.scalars(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == patient.patient_id,
            ConditionTracker.active.is_(True),
        )
    ).all()
    assert {item.condition_key for item in trackers} == {
        ConditionKey.HR_HIGH,
        ConditionKey.HR_LOW,
    }


def test_concurrent_older_resolution_and_newer_reactivation_use_newest_event(
    integration_engine,
    db_session,
    patient,
):
    concurrent_ingest(
        integration_engine,
        patient.patient_id,
        [
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "78",
                "recorded_at": BASE_TIME,
            },
            {
                "metric_type": MetricType.HEART_RATE,
                "numeric_value": "110",
                "recorded_at": BASE_TIME + timedelta(seconds=1),
            },
        ],
    )
    db_session.expire_all()
    tracker = db_session.scalar(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == patient.patient_id,
            ConditionTracker.condition_key == ConditionKey.HR_HIGH,
        )
    )
    assert tracker.active is True
    assert tracker.last_seen_at == BASE_TIME + timedelta(seconds=1)

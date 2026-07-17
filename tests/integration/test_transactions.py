from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import app.event_evaluations.service as evaluation_service
import app.health_events.service as ingestion_service
from app.condition_trackers.model import ConditionTracker
from app.event_evaluations.model import EventEvaluation
from app.health_events.model import HealthEvent, MetricType, ValidationStatus
from app.health_events.schema import HealthEventCreate

pytestmark = pytest.mark.integration


def event(patient):
    return HealthEventCreate(
        patient_id=patient.patient_id,
        metric_type=MetricType.HEART_RATE,
        numeric_value="110",
        recorded_at=datetime(2026, 7, 17, 5, tzinfo=timezone.utc),
        validation_status=ValidationStatus.VALID_REALTIME,
    )


def assert_empty(session):
    assert session.scalar(select(func.count(HealthEvent.event_id))) == 0
    assert session.scalar(select(func.count(EventEvaluation.evaluation_id))) == 0
    assert session.scalar(select(func.count(ConditionTracker.condition_tracker_id))) == 0


def test_evaluator_failure_rolls_back_entire_operation(db_session, patient, monkeypatch):
    monkeypatch.setattr(
        ingestion_service,
        "evaluate_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("evaluation")),
    )
    with pytest.raises(RuntimeError, match="evaluation"):
        ingestion_service.create_health_event(db_session, event(patient))
    assert_empty(db_session)


def test_tracker_failure_rolls_back_event_and_evaluation(
    db_session,
    patient,
    monkeypatch,
):
    monkeypatch.setattr(
        evaluation_service,
        "update_condition_tracker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("tracker")),
    )
    with pytest.raises(RuntimeError, match="tracker"):
        ingestion_service.create_health_event(db_session, event(patient))
    assert_empty(db_session)


def test_commit_failure_rolls_back_flushed_rows(
    integration_engine,
    db_session,
    patient,
):
    class FailingCommitSession(Session):
        def commit(self):
            raise RuntimeError("commit failed")

    failing = sessionmaker(
        bind=integration_engine,
        class_=FailingCommitSession,
        expire_on_commit=False,
    )()
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            ingestion_service.create_health_event(failing, event(patient))
    finally:
        failing.close()
    db_session.expire_all()
    assert_empty(db_session)


def test_valid_request_succeeds_after_failed_request(db_session, patient, monkeypatch):
    original = ingestion_service.evaluate_event
    monkeypatch.setattr(
        ingestion_service,
        "evaluate_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("once")),
    )
    with pytest.raises(RuntimeError):
        ingestion_service.create_health_event(db_session, event(patient))
    monkeypatch.setattr(ingestion_service, "evaluate_event", original)
    result = ingestion_service.create_health_event(db_session, event(patient))
    assert result.event_id is not None

from datetime import datetime
import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.condition_trackers.model import ConditionTracker
from app.core.time import utc_now
from app.event_evaluations.model import (
    ConditionKey,
    EventEvaluation,
    MonitoringState,
)
from app.health_events.model import HealthEvent, MetricType

RESOLVABLE_CONDITIONS: dict[MetricType, list[ConditionKey]] = {
    MetricType.HEART_RATE: [
        ConditionKey.HR_HIGH,
        ConditionKey.HR_LOW,
    ],
    MetricType.SPO2: [
        ConditionKey.SPO2_LOW,
    ],
}


NORMAL_CONDITIONS = {
    ConditionKey.HR_NORMAL,
    ConditionKey.SPO2_NORMAL,
}

STATE_RANK = {
    MonitoringState.STABLE: 0,
    MonitoringState.RESOLVED: 0,
    MonitoringState.UNKNOWN: 0,
    MonitoringState.ELEVATED: 1,
    MonitoringState.WARNING: 2,
    MonitoringState.CRITICAL: 3,
}


def _signed_int32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value if value < 0x80000000 else value - 0x100000000


def _lock_tracker_key(
    db: Session,
    patient_id,
    condition_key: ConditionKey,
) -> None:
    """Serialize one patient/condition stream without blocking other keys."""
    patient_key = _signed_int32(patient_id.int)
    condition_key_hash = int.from_bytes(
        hashlib.blake2s(condition_key.value.encode(), digest_size=4).digest(),
    )
    db.execute(
        select(
            func.pg_advisory_xact_lock(
                patient_key,
                _signed_int32(condition_key_hash),
            )
        )
    )


def _get_tracker(
    db: Session,
    event: HealthEvent,
    condition_key: ConditionKey,
) -> ConditionTracker | None:
    return db.scalar(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == event.patient_id,
            ConditionTracker.condition_key == condition_key,
        )
    )


def _should_apply_event(
    db: Session,
    tracker: ConditionTracker,
    event: HealthEvent,
    incoming_state: MonitoringState,
) -> bool:
    if event.recorded_at > tracker.last_seen_at:
        return True
    if event.recorded_at < tracker.last_seen_at:
        return False

    # Equal observation times never reduce severity. For equal severity, the
    # later-ingested event (created_at, then UUID) wins deterministically.
    current_evaluation = db.scalar(
        select(EventEvaluation).where(
            EventEvaluation.event_id == tracker.last_event_id,
        )
    )
    current_state = (
        current_evaluation.new_state
        if current_evaluation is not None
        else MonitoringState.STABLE
    )
    if STATE_RANK[incoming_state] != STATE_RANK[current_state]:
        return STATE_RANK[incoming_state] > STATE_RANK[current_state]

    current_event = db.get(HealthEvent, tracker.last_event_id)
    if current_event is None:
        return True
    return (event.created_at, event.event_id.int) > (
        current_event.created_at,
        current_event.event_id.int,
    )


def update_condition_tracker(
    db: Session,
    event: HealthEvent,
    evaluation: EventEvaluation,
) -> ConditionTracker | None:
    now = utc_now()

    if evaluation.new_state == MonitoringState.STABLE:
        return resolve_metric_conditions(
            db=db,
            event=event,
            now=now,
        )

    # Normal classifications should never create condition trackers.
    if evaluation.condition_key in NORMAL_CONDITIONS:
        return None

    _lock_tracker_key(db, event.patient_id, evaluation.condition_key)
    tracker = _get_tracker(db, event, evaluation.condition_key)

    if tracker is None:
        tracker = ConditionTracker(
            patient_id=event.patient_id,
            last_event_id=event.event_id,
            condition_key=evaluation.condition_key,
            active=True,
            started_at=event.recorded_at,
            last_seen_at=event.recorded_at,
            confirmed_at=(
                now if evaluation.new_state == MonitoringState.CRITICAL else None
            ),
        )

        db.add(tracker)

    elif _should_apply_event(db, tracker, event, evaluation.new_state):
        # Start a new occurrence period when a previously resolved
        # condition becomes active again.
        if not tracker.active:
            tracker.started_at = event.recorded_at
            tracker.confirmed_at = None

        tracker.last_event_id = event.event_id
        tracker.last_seen_at = event.recorded_at
        tracker.active = True
        tracker.updated_at = now

        if (
            tracker.confirmed_at is None
            and evaluation.new_state == MonitoringState.CRITICAL
        ):
            tracker.confirmed_at = now

    db.flush()

    return tracker


def resolve_metric_conditions(
    db: Session,
    event: HealthEvent,
    now: datetime,
) -> ConditionTracker | None:
    condition_keys = RESOLVABLE_CONDITIONS.get(event.metric_type, [])

    if not condition_keys:
        return None

    trackers: list[ConditionTracker] = []
    for condition_key in sorted(condition_keys, key=lambda key: key.value):
        _lock_tracker_key(db, event.patient_id, condition_key)
        tracker = _get_tracker(db, event, condition_key)

        # Inactive rows also serve as ordering watermarks. This prevents an
        # older abnormal event from reactivating a condition after a newer
        # normal reading was ingested first.
        if tracker is None:
            tracker = ConditionTracker(
                patient_id=event.patient_id,
                last_event_id=event.event_id,
                condition_key=condition_key,
                active=False,
                started_at=event.recorded_at,
                last_seen_at=event.recorded_at,
            )
            db.add(tracker)
            trackers.append(tracker)
        elif _should_apply_event(db, tracker, event, MonitoringState.STABLE):
            tracker.active = False
            tracker.last_event_id = event.event_id
            tracker.last_seen_at = event.recorded_at
            tracker.updated_at = now
            trackers.append(tracker)

    db.flush()

    return trackers[0] if trackers else None

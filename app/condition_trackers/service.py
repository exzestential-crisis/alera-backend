from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.condition_trackers.model import ConditionTracker
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


def update_condition_tracker(
    db: Session,
    event: HealthEvent,
    evaluation: EventEvaluation,
) -> ConditionTracker | None:
    now = datetime.now(timezone.utc)

    if evaluation.new_state == MonitoringState.STABLE:
        return resolve_metric_conditions(
            db=db,
            event=event,
            now=now,
        )

    # Normal classifications should never create condition trackers.
    if evaluation.condition_key in NORMAL_CONDITIONS:
        return None

    tracker = db.scalar(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == event.patient_id,
            ConditionTracker.condition_key == evaluation.condition_key,
        )
    )

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

    else:
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

    trackers = db.scalars(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == event.patient_id,
            ConditionTracker.condition_key.in_(condition_keys),
            ConditionTracker.active.is_(True),
        )
    ).all()

    if not trackers:
        return None

    for tracker in trackers:
        tracker.active = False
        tracker.last_event_id = event.event_id
        tracker.last_seen_at = event.recorded_at
        tracker.updated_at = now

    db.flush()

    return trackers[0]

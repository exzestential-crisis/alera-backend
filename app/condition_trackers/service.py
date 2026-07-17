from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.condition_trackers.model import ConditionTracker
from app.event_evaluations.model import (
    ConditionKey,
    EventEvaluation,
    MonitoringState,
)
from app.health_events.model import HealthEvent


def update_condition_tracker(
    db: Session,
    event: HealthEvent,
    evaluation: EventEvaluation,
) -> ConditionTracker | None:
    tracker = db.scalar(
        select(ConditionTracker).where(
            ConditionTracker.patient_id == event.patient_id,
            ConditionTracker.condition_key == evaluation.condition_key,
        )
    )

    now = datetime.now(timezone.utc)

    if evaluation.new_state == MonitoringState.STABLE:
        heart_rate_conditions = [
            ConditionKey.HR_HIGH,
            ConditionKey.HR_LOW,
        ]

        trackers = db.scalars(
            select(ConditionTracker).where(
                ConditionTracker.patient_id == event.patient_id,
                ConditionTracker.condition_key.in_(heart_rate_conditions),
                ConditionTracker.active.is_(True),
            )
        ).all()

        if not trackers:
            return None

        for active_tracker in trackers:
            active_tracker.active = False
            active_tracker.last_event_id = event.event_id
            active_tracker.last_seen_at = event.recorded_at
            active_tracker.updated_at = now

        db.commit()

        return trackers[0]

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
        tracker.last_event_id = event.event_id
        tracker.last_seen_at = event.recorded_at
        tracker.active = True
        tracker.updated_at = now

        if (
            tracker.confirmed_at is None
            and evaluation.new_state == MonitoringState.CRITICAL
        ):
            tracker.confirmed_at = now

    db.commit()
    db.refresh(tracker)

    return tracker

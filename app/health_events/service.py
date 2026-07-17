from sqlalchemy.orm import Session

from app.event_evaluations.service import evaluate_heart_rate_event
from app.health_events.model import HealthEvent
from app.health_events.schema import HealthEventCreate


def create_health_event(
    db: Session,
    event_data: HealthEventCreate,
) -> HealthEvent:
    try:
        health_event = HealthEvent(
            **event_data.model_dump(),
        )

        db.add(health_event)

        # Sends the INSERT to PostgreSQL without committing.
        # This gives health_event its generated event_id.
        db.flush()

        evaluate_heart_rate_event(
            db=db,
            event=health_event,
        )

        # Commit the event, evaluation, and tracker together.
        db.commit()
        db.refresh(health_event)

        return health_event

    except Exception:
        db.rollback()
        raise

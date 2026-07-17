from sqlalchemy.orm import Session

from app.event_evaluations.service import evaluate_event
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
        db.flush()

        evaluate_event(
            db=db,
            event=health_event,
        )

        db.commit()
        db.refresh(health_event)

        return health_event

    except Exception:
        db.rollback()
        raise

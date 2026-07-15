from sqlalchemy.orm import Session

from app.health_events.model import HealthEvent
from app.health_events.schema import HealthEventCreate


def create_health_event(
    db: Session,
    event_data: HealthEventCreate,
) -> HealthEvent:
    health_event = HealthEvent(
        **event_data.model_dump(),
    )

    db.add(health_event)
    db.commit()
    db.refresh(health_event)

    return health_event
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.health_events.schema import (
    HealthEventCreate,
    HealthEventResponse,
)
from app.health_events.service import create_health_event

router = APIRouter(
    prefix="/api/v1/health-events",
    tags=["Health Events"],
)


@router.post(
    "",
    response_model=HealthEventResponse,
)
def create_event(
    event: HealthEventCreate,
    db: Session = Depends(get_db),
):
    return create_health_event(db, event)
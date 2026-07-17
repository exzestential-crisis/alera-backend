from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event_evaluations.service import evaluate_event
from app.health_events.errors import (
    ExternalEventConflictError,
    HealthEventConstraintError,
    PatientNotFoundError,
)
from app.health_events.model import HealthEvent, ValidationStatus
from app.health_events.schema import HealthEventCreate
from app.patients.model import ElderlyPatient


def _payload_matches(
    existing: HealthEvent,
    event_data: HealthEventCreate,
) -> bool:
    return all(
        getattr(existing, field_name) == field_value
        for field_name, field_value in event_data.model_dump().items()
    )


def _find_external_event(
    db: Session,
    external_event_id: str | None,
) -> HealthEvent | None:
    if external_event_id is None:
        return None
    return db.scalar(
        select(HealthEvent).where(
            HealthEvent.external_event_id == external_event_id,
        )
    )


def _resolve_duplicate(
    existing: HealthEvent,
    event_data: HealthEventCreate,
) -> HealthEvent:
    if not _payload_matches(existing, event_data):
        raise ExternalEventConflictError(
            "external_event_id is already used by a different event."
        )
    return existing


def create_health_event(
    db: Session,
    event_data: HealthEventCreate,
) -> HealthEvent:
    try:
        patient = db.get(ElderlyPatient, event_data.patient_id)
        if patient is None:
            raise PatientNotFoundError("Patient not found.")

        existing = _find_external_event(db, event_data.external_event_id)
        if existing is not None:
            result = _resolve_duplicate(existing, event_data)
            db.commit()
            return result

        health_event = HealthEvent(
            **event_data.model_dump(),
        )

        db.add(health_event)
        db.flush()

        if event_data.validation_status != ValidationStatus.INVALID:
            evaluate_event(
                db=db,
                event=health_event,
            )

        db.commit()

        return health_event

    except IntegrityError as exc:
        db.rollback()
        existing = _find_external_event(db, event_data.external_event_id)
        if existing is not None:
            result = _resolve_duplicate(existing, event_data)
            db.commit()
            return result
        db.rollback()
        raise HealthEventConstraintError(
            "Health event conflicts with current database state."
        ) from exc
    except Exception:
        db.rollback()
        raise

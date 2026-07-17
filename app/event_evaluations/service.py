from decimal import Decimal

from sqlalchemy.orm import Session

from app.condition_trackers.service import update_condition_tracker
from app.event_evaluations.model import (
    ConditionKey,
    EvaluationSeverity,
    EventEvaluation,
    MonitoringState,
)
from app.health_events.model import HealthEvent, MetricType
from app.patients.model import ElderlyPatient


def evaluate_heart_rate_event(
    db: Session,
    event: HealthEvent,
) -> EventEvaluation | None:
    if event.metric_type != MetricType.HEART_RATE:
        return None

    if event.numeric_value is None:
        return None

    patient = db.get(ElderlyPatient, event.patient_id)

    if patient is None:
        raise ValueError("Patient not found")

    value = Decimal(event.numeric_value)

    if value > Decimal("150"):
        condition = ConditionKey.HR_HIGH
        threshold = Decimal("150")
        new_state = MonitoringState.CRITICAL
        severity = EvaluationSeverity.CRITICAL
        reason = (
            f"Heart rate {value} bpm exceeded the critical threshold of " f"150 bpm."
        )

    elif value > patient.normal_hr_max:
        condition = ConditionKey.HR_HIGH
        threshold = Decimal(patient.normal_hr_max)
        new_state = MonitoringState.ELEVATED
        severity = EvaluationSeverity.WARNING
        reason = (
            f"Heart rate {value} bpm exceeded the patient's normal maximum "
            f"of {patient.normal_hr_max} bpm."
        )

    elif value < patient.normal_hr_min:
        condition = ConditionKey.HR_LOW
        threshold = Decimal(patient.normal_hr_min)
        new_state = MonitoringState.ELEVATED
        severity = EvaluationSeverity.WARNING
        reason = (
            f"Heart rate {value} bpm fell below the patient's normal minimum "
            f"of {patient.normal_hr_min} bpm."
        )

    else:
        condition = ConditionKey.HR_HIGH
        threshold = None
        new_state = MonitoringState.STABLE
        severity = EvaluationSeverity.INFO
        reason = f"Heart rate {value} bpm is within the patient's expected range."

    evaluation = EventEvaluation(
        event_id=event.event_id,
        alert_id=None,
        condition_key=condition,
        threshold_value_used=threshold,
        threshold_met=new_state != MonitoringState.STABLE,
        persistence_met=False,
        previous_state=MonitoringState.UNKNOWN,
        new_state=new_state,
        severity=severity,
        evaluation_reason=reason,
    )

    db.add(evaluation)

    # Assigns the generated evaluation_id while keeping
    # the overall ingestion transaction open.
    db.flush()

    update_condition_tracker(
        db=db,
        event=event,
        evaluation=evaluation,
    )

    return evaluation


def evaluate_event(
    db: Session,
    event: HealthEvent,
) -> EventEvaluation | None:
    """
    Dispatches a health event to the appropriate metric evaluator.
    """

    if event.metric_type == MetricType.HEART_RATE:
        return evaluate_heart_rate_event(
            db=db,
            event=event,
        )

    return None

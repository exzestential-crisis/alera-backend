from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.health_events.model import MetricType, ValidationStatus

class HealthEventCreate(BaseModel):
    patient_id: UUID
    external_event_id: str | None = Field(default=None, max_length=150)

    metric_type: MetricType

    numeric_value: Decimal | None = None
    text_value: str | None = Field(default=None, max_length=100)
    boolean_value: bool | None = None

    metric_unit: str | None = Field(default=None, max_length=30)

    recorded_at: datetime
    validation_status: ValidationStatus
    validation_reason: str | None = None

    raw_payload: dict = Field(default_factory=dict)

class HealthEventResponse(HealthEventCreate):
    event_id: UUID
    received_at: datetime
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
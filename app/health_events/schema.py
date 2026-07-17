from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_metric_value(self) -> "HealthEventCreate":
        if self.metric_type == MetricType.HEART_RATE:
            if self.numeric_value is None:
                raise ValueError("numeric_value is required for HEART_RATE.")
            if not self.numeric_value.is_finite() or self.numeric_value <= 0:
                raise ValueError("Heart rate must be greater than 0 bpm.")

        if self.metric_type == MetricType.SPO2:
            if self.numeric_value is None:
                raise ValueError("numeric_value is required for SPO2.")
            if not self.numeric_value.is_finite() or not 0 <= self.numeric_value <= 100:
                raise ValueError("SpO₂ must be between 0 and 100 percent.")

        return self


class HealthEventResponse(HealthEventCreate):
    event_id: UUID
    received_at: datetime
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }

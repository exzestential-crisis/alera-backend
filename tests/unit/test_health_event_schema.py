from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.health_events.model import MetricType, ValidationStatus
from app.health_events.schema import HealthEventCreate


def payload(**changes):
    data = {
        "patient_id": uuid4(),
        "metric_type": MetricType.HEART_RATE,
        "numeric_value": Decimal("78"),
        "recorded_at": datetime(2026, 7, 17, 5, tzinfo=timezone.utc),
        "validation_status": ValidationStatus.VALID_REALTIME,
    }
    data.update(changes)
    return data


@pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("-1")])
def test_heart_rate_rejects_missing_or_nonpositive_values(value):
    with pytest.raises(ValidationError):
        HealthEventCreate.model_validate(payload(numeric_value=value))


@pytest.mark.parametrize("value", [None, Decimal("-1"), Decimal("100.01")])
def test_spo2_rejects_missing_or_out_of_range_values(value):
    with pytest.raises(ValidationError):
        HealthEventCreate.model_validate(
            payload(metric_type=MetricType.SPO2, numeric_value=value)
        )


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("97"), Decimal("100")])
def test_spo2_accepts_storage_contract_boundaries(value):
    event = HealthEventCreate.model_validate(
        payload(metric_type=MetricType.SPO2, numeric_value=value)
    )
    assert event.numeric_value == value.quantize(Decimal("0.01"))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_values_are_rejected(value):
    with pytest.raises(ValidationError):
        HealthEventCreate.model_validate(payload(numeric_value=value))


def test_numeric_value_is_rounded_half_up_to_database_scale():
    event = HealthEventCreate.model_validate(payload(numeric_value="150.995"))
    assert event.numeric_value == Decimal("151.00")


def test_numeric_overflow_is_rejected():
    with pytest.raises(ValidationError, match=r"NUMERIC\(10,2\)"):
        HealthEventCreate.model_validate(payload(numeric_value="100000000"))


def test_naive_recorded_at_is_rejected():
    with pytest.raises(ValidationError, match="timezone offset"):
        HealthEventCreate.model_validate(
            payload(recorded_at=datetime(2026, 7, 17, 5))
        )


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-07-17T05:00:00Z", datetime(2026, 7, 17, 5, tzinfo=timezone.utc)),
        ("2026-07-17T13:00:00+08:00", datetime(2026, 7, 17, 5, tzinfo=timezone.utc)),
        ("2026-07-16T21:00:00-08:00", datetime(2026, 7, 17, 5, tzinfo=timezone.utc)),
        ("2026-03-08T01:00:00-04:00", datetime(2026, 3, 8, 5, tzinfo=timezone.utc)),
    ],
)
def test_aware_recorded_at_is_normalized_to_utc(timestamp, expected):
    event = HealthEventCreate.model_validate(payload(recorded_at=timestamp))
    assert event.recorded_at == expected
    assert event.recorded_at.tzinfo is timezone.utc


def test_invalid_event_requires_reason_and_may_omit_metric_value():
    with pytest.raises(ValidationError, match="validation_reason is required"):
        HealthEventCreate.model_validate(
            payload(validation_status=ValidationStatus.INVALID, numeric_value=None)
        )

    event = HealthEventCreate.model_validate(
        payload(
            validation_status=ValidationStatus.INVALID,
            validation_reason="sensor rejected reading",
            numeric_value=None,
        )
    )
    assert event.numeric_value is None


def test_valid_realtime_event_rejects_validation_reason():
    with pytest.raises(ValidationError, match="must not be provided"):
        HealthEventCreate.model_validate(payload(validation_reason="not valid"))


def test_delayed_usable_event_may_include_reason():
    event = HealthEventCreate.model_validate(
        payload(
            validation_status=ValidationStatus.DELAYED_USABLE,
            validation_reason="uploaded after reconnect",
        )
    )
    assert event.validation_reason == "uploaded after reconnect"

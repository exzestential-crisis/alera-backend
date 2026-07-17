from types import SimpleNamespace

import pytest

from app.patients.model import validate_patient_thresholds


def thresholds(hr_min=60, hr_max=100, spo2_min=95, spo2_max=None):
    return SimpleNamespace(
        normal_hr_min=hr_min,
        normal_hr_max=hr_max,
        usual_spo2_min=spo2_min,
        usual_spo2_max=spo2_max,
    )


@pytest.mark.parametrize(
    "patient",
    [
        thresholds(hr_min=0),
        thresholds(hr_max=-1),
        thresholds(hr_min=101, hr_max=100),
        thresholds(spo2_min=-1),
        thresholds(spo2_min=101),
        thresholds(spo2_max=-1),
        thresholds(spo2_max=101),
        thresholds(spo2_min=96, spo2_max=95),
    ],
)
def test_invalid_thresholds_are_rejected(patient):
    with pytest.raises(ValueError):
        validate_patient_thresholds(patient)


@pytest.mark.parametrize(
    "patient",
    [
        thresholds(hr_min=60, hr_max=60),
        thresholds(hr_max=180),
        thresholds(spo2_min=0, spo2_max=0),
        thresholds(spo2_min=100, spo2_max=100),
        thresholds(spo2_min=92, spo2_max=99),
    ],
)
def test_valid_thresholds_are_accepted(patient):
    validate_patient_thresholds(patient)

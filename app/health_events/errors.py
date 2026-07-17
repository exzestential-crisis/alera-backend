class HealthEventError(Exception):
    """Base class for expected health-event ingestion failures."""


class PatientNotFoundError(HealthEventError):
    pass


class ExternalEventConflictError(HealthEventError):
    pass


class HealthEventConstraintError(HealthEventError):
    pass

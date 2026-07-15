import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sex(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class HealthPlatform(str, enum.Enum):
    HEALTH_CONNECT = "HEALTH_CONNECT"
    SIMULATOR = "SIMULATOR"
    MANUAL_TEST = "MANUAL_TEST"


class IntegrationStatus(str, enum.Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    SYNCING = "SYNCING"
    FAILED = "FAILED"
    DISCONNECTED = "DISCONNECTED"


class ElderlyPatient(Base):
    __tablename__ = "elderly_patients"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.household_id"),
        nullable=False,
    )

    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birthdate: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Sex] = mapped_column(Enum(Sex, name="patient_sex"), nullable=False)

    known_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    doctor_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    normal_hr_min: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    normal_hr_max: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    usual_spo2_min: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    usual_spo2_max: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    health_platform: Mapped[HealthPlatform] = mapped_column(
        Enum(HealthPlatform, name="health_platform"),
        nullable=False,
        default=HealthPlatform.SIMULATOR,
    )

    device_brand: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    integration_status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus, name="integration_status"),
        nullable=False,
        default=IntegrationStatus.NOT_CONNECTED,
    )

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
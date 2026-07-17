import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def migrate(database_url, operation, revision):
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        config = Config(str(ROOT / "alembic.ini"))
        getattr(command, operation)(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_fresh_upgrade_downgrade_and_reupgrade(test_database_url):
    base_url = make_url(test_database_url)
    database_name = f"alera_migration_test_{uuid4().hex[:10]}"
    temporary_url = base_url.set(database=database_name)
    admin_url = base_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')

    engine = create_engine(temporary_url)
    try:
        migrate(temporary_url.render_as_string(hide_password=False), "upgrade", "head")
        inspector = inspect(engine)
        assert {
            "users",
            "households",
            "elderly_patients",
            "health_events",
            "event_evaluations",
            "condition_trackers",
        }.issubset(inspector.get_table_names())

        assert {item["column_names"][0] for item in inspector.get_unique_constraints(
            "health_events"
        )} == {"external_event_id"}
        tracker_uniques = inspector.get_unique_constraints("condition_trackers")
        assert any(
            item["name"] == "uq_condition_trackers_patient_condition"
            and item["column_names"] == ["patient_id", "condition_key"]
            for item in tracker_uniques
        )

        patient_columns = {
            column["name"]: column for column in inspector.get_columns("elderly_patients")
        }
        assert patient_columns["normal_hr_min"]["nullable"] is False
        assert patient_columns["normal_hr_max"]["nullable"] is False
        assert patient_columns["usual_spo2_min"]["nullable"] is False
        assert str(patient_columns["normal_hr_min"]["default"]) == "60"
        assert str(patient_columns["normal_hr_max"]["default"]) == "100"
        assert str(patient_columns["usual_spo2_min"]["default"]) == "95"

        checks = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("elderly_patients")
        }
        assert {
            "ck_patient_hr_min_positive",
            "ck_patient_hr_max_positive",
            "ck_patient_hr_range_order",
            "ck_patient_spo2_min_range",
            "ck_patient_spo2_max_range",
            "ck_patient_spo2_range_order",
        }.issubset(checks)

        with engine.connect() as connection:
            metric_values = set(
                connection.execute(
                    text(
                        "SELECT enumlabel FROM pg_enum "
                        "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                        "WHERE pg_type.typname = 'metric_type'"
                    )
                ).scalars()
            )
        assert {"HEART_RATE", "SPO2", "ACTIVITY", "SLEEP"}.issubset(metric_values)

        migrate(
            temporary_url.render_as_string(hide_password=False),
            "downgrade",
            "0f4ec5017182",
        )
        with engine.connect() as connection:
            enum_values = connection.execute(
                text(
                    "SELECT enumlabel FROM pg_enum "
                    "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                    "WHERE pg_type.typname = 'condition_key'"
                )
            ).scalars().all()
        # PostgreSQL enum values are intentionally retained by the existing
        # partially irreversible downgrade.
        assert "HR_NORMAL" in enum_values
        assert "SPO2_NORMAL" in enum_values

        migrate(temporary_url.render_as_string(hide_password=False), "upgrade", "head")
        assert "ck_patient_hr_range_order" in {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints(
                "elderly_patients"
            )
        }
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin_engine.dispose()

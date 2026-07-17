from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.database import create_db_engine
from app.main import create_app


def test_health_check_does_not_require_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app(
        Settings(
            app_name="Alera Test",
            environment="testing",
            database_url=None,
        )
    )
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Alera Test",
        "environment": "testing",
    }


def test_sql_echo_is_disabled_by_default(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.db.database.create_engine", fake_create_engine)
    create_db_engine(Settings(database_url="postgresql+psycopg://test/test"))
    assert captured["echo"] is False

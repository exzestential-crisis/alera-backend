"""Explicit database connectivity diagnostic; not imported by pytest."""

from sqlalchemy import text

from app.db.database import get_engine


def main() -> None:
    with get_engine().connect() as connection:
        print(connection.execute(text("SELECT version()")).scalar())


if __name__ == "__main__":
    main()

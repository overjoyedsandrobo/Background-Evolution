import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app.db import get_db
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/background_evolution_test",
)


@pytest.fixture(scope="session")
def db_engine():
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    command.upgrade(alembic_cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    # Standard SQLAlchemy "join an external transaction" test recipe: app
    # code (crud.py) legitimately calls session.commit(), so we nest every
    # commit inside a SAVEPOINT and only roll back the outer connection-level
    # transaction at teardown, keeping each test isolated regardless of how
    # many times the code under test commits.
    connection = db_engine.connect()
    outer_transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def seeded_db_session(db_session) -> Session:
    crud.ensure_default_slots(db_session, 3)
    return db_session


@pytest.fixture
def client(seeded_db_session):
    # Deliberately not used as a context manager: that would run FastAPI's
    # startup event, which seeds slots via its own SessionLocal against
    # settings.database_url (the real dev DB) instead of the per-test
    # transactional session below. seeded_db_session already seeds the slots
    # this test needs.
    def _get_db_override():
        yield seeded_db_session

    app.dependency_overrides[get_db] = _get_db_override
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

from alembic import command
from alembic.config import Config

from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


def test_upgrade_downgrade_roundtrip(db_engine):
    # db_engine fixture already ran upgrade head; verify a full round trip
    # leaves the schema in the same (head) state.
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

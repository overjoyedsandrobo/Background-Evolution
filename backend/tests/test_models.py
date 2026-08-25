import pytest
from sqlalchemy.exc import IntegrityError

from app.models import EnvironmentTimeSeconds, KnownEnvironment, SaveSlot


def _make_slot(db_session, slot_id=0):
    slot = SaveSlot(id=slot_id, environment_slot_keys=["water", "earth", "air", "fire"])
    db_session.add(slot)
    db_session.commit()
    return slot


def test_duplicate_environment_time_key_rejected(db_session):
    _make_slot(db_session)
    db_session.add(EnvironmentTimeSeconds(slot_id=0, environment_key="fire", seconds=1.0))
    db_session.commit()
    db_session.add(EnvironmentTimeSeconds(slot_id=0, environment_key="fire", seconds=2.0))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_cascade_delete_removes_children(db_session):
    slot = _make_slot(db_session)
    db_session.add(EnvironmentTimeSeconds(slot_id=0, environment_key="fire", seconds=1.0))
    db_session.add(
        KnownEnvironment(
            slot_id=0, name="volcano", weights={"fire": 1.0}, traits={}, generation=1, parents=[]
        )
    )
    db_session.commit()

    db_session.delete(slot)
    db_session.commit()

    assert db_session.query(EnvironmentTimeSeconds).filter_by(slot_id=0).count() == 0
    assert db_session.query(KnownEnvironment).filter_by(slot_id=0).count() == 0


def test_evolution_click_progress_check_constraint(db_session):
    slot = SaveSlot(
        id=0,
        environment_slot_keys=["water", "earth", "air", "fire"],
        evolution_click_progress=5,
    )
    db_session.add(slot)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_evolution_stage_check_constraint(db_session):
    slot = SaveSlot(
        id=0,
        environment_slot_keys=["water", "earth", "air", "fire"],
        evolution_stage="not-a-real-stage",
    )
    db_session.add(slot)
    with pytest.raises(IntegrityError):
        db_session.commit()

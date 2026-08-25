"""Database access + game-state orchestration.

This is the server-side home for what used to be main.py's
ensure_environment_known / get_generation_parent_keys /
generate_hidden_environment_from_progress / save_active_slot / enter_slot /
reset_current_progress closures, now operating on SQLAlchemy rows instead of
`nonlocal` variables.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.game_engine.environment_generator import BASE_ENVIRONMENTS, Environment, World
from app.models import EnvironmentTimeSeconds, KnownEnvironment, SaveSlot
from app.progression import should_reveal_hidden_environment

DEFAULT_ENVIRONMENT_SLOT_KEYS = ["water", "earth", "air", "fire"]
GENERATOR_PARENT_ORDER = ["air", "earth", "fire", "water"]


class SlotNotFoundError(LookupError):
    pass


def ensure_default_slots(db: Session, num_slots: int) -> None:
    existing_ids = {row.id for row in db.execute(select(SaveSlot.id)).all()}
    for slot_id in range(num_slots):
        if slot_id in existing_ids:
            continue
        slot = SaveSlot(id=slot_id, environment_slot_keys=list(DEFAULT_ENVIRONMENT_SLOT_KEYS))
        db.add(slot)
        db.flush()
        for key in DEFAULT_ENVIRONMENT_SLOT_KEYS:
            db.add(EnvironmentTimeSeconds(slot_id=slot.id, environment_key=key, seconds=0.0))
    db.commit()


def list_slots(db: Session) -> list[SaveSlot]:
    return list(db.execute(select(SaveSlot).order_by(SaveSlot.id)).scalars())


def get_slot(db: Session, slot_id: int) -> SaveSlot:
    slot = db.get(SaveSlot, slot_id)
    if slot is None:
        raise SlotNotFoundError(f"Slot {slot_id} not found")
    return slot


def slot_detail_dict(slot: SaveSlot) -> dict:
    return {
        "id": slot.id,
        "used": slot.used,
        "current_tab": slot.current_tab,
        "evolution_stage": slot.evolution_stage,
        "time_alive_seconds": slot.time_alive_seconds,
        "evolution_click_progress": slot.evolution_click_progress,
        "selected_environment": slot.selected_environment,
        "hidden_revealed": slot.hidden_revealed,
        "hidden_environment_name": slot.hidden_environment_name,
        "hidden_cycle_index": slot.hidden_cycle_index,
        "hidden_slot_index": slot.hidden_slot_index,
        "environment_slot_keys": list(slot.environment_slot_keys),
        "awaiting_hidden_relock_choice": slot.awaiting_hidden_relock_choice,
        "environment_time_seconds": {
            row.environment_key: row.seconds for row in slot.environment_times
        },
        "known_environments": {
            row.name: {
                "name": row.name,
                "weights": row.weights,
                "traits": row.traits,
                "tier": row.tier,
                "parents": row.parents,
            }
            for row in slot.known_environments
        },
    }


def _reset_common_fields(slot: SaveSlot) -> None:
    slot.used = True
    slot.current_tab = "stats"
    slot.time_alive_seconds = 0.0
    slot.evolution_stage = "dormant"
    slot.evolution_click_progress = 0
    slot.selected_environment = None
    slot.hidden_revealed = False
    slot.hidden_environment_name = None
    slot.hidden_cycle_index = 1
    slot.hidden_slot_index = 3
    slot.environment_slot_keys = list(DEFAULT_ENVIRONMENT_SLOT_KEYS)
    slot.awaiting_hidden_relock_choice = False


def _reset_environment_times(slot: SaveSlot) -> None:
    # Update rows in place for keys that survive the reset rather than
    # clear()-then-append: deleting and re-inserting a row with the same
    # (slot_id, environment_key) in one flush races the unique constraint,
    # since SQLAlchemy's unit of work emits inserts before deletes.
    active_keys = DEFAULT_ENVIRONMENT_SLOT_KEYS
    existing = {row.environment_key: row for row in slot.environment_times}
    for key, row in list(existing.items()):
        if key not in active_keys:
            slot.environment_times.remove(row)
    for key in active_keys:
        row = existing.get(key)
        if row is not None:
            row.seconds = 0.0
        else:
            slot.environment_times.append(EnvironmentTimeSeconds(environment_key=key, seconds=0.0))


def new_slot(db: Session, slot_id: int) -> SaveSlot:
    """Full wipe: fresh game in this slot, discovered environments included."""
    slot = get_slot(db, slot_id)
    _reset_common_fields(slot)
    _reset_environment_times(slot)
    slot.known_environments.clear()
    db.commit()
    db.refresh(slot)
    return slot


def reset_slot(db: Session, slot_id: int) -> SaveSlot:
    """Soft reset: the in-game Reset button. Keeps discovered environments."""
    slot = get_slot(db, slot_id)
    _reset_common_fields(slot)
    _reset_environment_times(slot)
    db.commit()
    db.refresh(slot)
    return slot


def ensure_environment_known(db: Session, slot: SaveSlot, env_name: str | None) -> bool:
    # Base environment keys are always lowercase (they're the hardcoded
    # slot-key vocabulary), but generated names carry whatever case
    # naming.compose_name produced - only fold case for the base check.
    env_name = str(env_name or "")
    if not env_name:
        return False
    if env_name.lower() in BASE_ENVIRONMENTS:
        return True
    return any(row.name == env_name for row in slot.known_environments)


def get_environment_dict(slot: SaveSlot, name: str) -> dict | None:
    name = str(name or "")
    if name.lower() in BASE_ENVIRONMENTS:
        base = BASE_ENVIRONMENTS[name.lower()]
        return {
            "name": base.name,
            "weights": base.weights,
            "traits": base.traits,
            "tier": base.tier,
            "parents": base.parents,
        }
    row = next((r for r in slot.known_environments if r.name == name), None)
    if row is None:
        return None
    return {
        "name": row.name,
        "weights": row.weights,
        "traits": row.traits,
        "tier": row.tier,
        "parents": row.parents,
    }


def build_world_for_slot(slot: SaveSlot) -> World:
    world = World()
    for row in slot.known_environments:
        world.environments[row.name] = Environment(
            name=row.name,
            weights=dict(row.weights),
            traits=dict(row.traits),
            tier=row.tier,
            parents=list(row.parents),
        )
    return world


def get_generation_parent_keys(db: Session, slot: SaveSlot) -> list[str]:
    active_keys = [
        key for key in slot.environment_slot_keys if ensure_environment_known(db, slot, key)
    ]
    ordered: list[str] = []
    for key in GENERATOR_PARENT_ORDER:
        if key in active_keys and key not in ordered:
            ordered.append(key)
    for key in active_keys:
        if key not in ordered:
            ordered.append(key)
    for key in GENERATOR_PARENT_ORDER:
        if len(ordered) >= 4:
            break
        if key not in ordered and ensure_environment_known(db, slot, key):
            ordered.append(key)
    return ordered[:4]


def _upsert_known_environment(db: Session, slot: SaveSlot, env: Environment) -> None:
    existing = next((row for row in slot.known_environments if row.name == env.name), None)
    if existing is not None:
        existing.weights = dict(env.weights)
        existing.traits = dict(env.traits)
        existing.tier = env.tier
        existing.parents = list(env.parents)
    else:
        slot.known_environments.append(
            KnownEnvironment(
                name=env.name,
                weights=dict(env.weights),
                traits=dict(env.traits),
                tier=env.tier,
                parents=list(env.parents),
            )
        )
    db.flush()


def generate_environment_for_slot(db: Session, slot: SaveSlot) -> str:
    """Combine the slot's 4 active parent environments into a new one.

    Mirrors generate_hidden_environment_from_progress() from the old
    monolith: on any failure (fewer than 4 known parents, generation error)
    it falls back to "fire", same as before.
    """
    parent_keys = get_generation_parent_keys(db, slot)
    if len(parent_keys) < 4:
        return "fire"
    times = {row.environment_key: row.seconds for row in slot.environment_times}
    times_list = [max(0.0, times.get(k, 0.0)) for k in parent_keys]
    total = sum(times_list)
    ratios = [0.25] * 4 if total <= 0.0 else [t / total for t in times_list]
    world = build_world_for_slot(slot)
    try:
        generated_env = world.generate(parent_keys, ratios)
    except Exception:
        return "fire"
    _upsert_known_environment(db, slot, generated_env)
    return generated_env.name


def _apply_environment_time_seconds(
    db: Session, slot: SaveSlot, provided: dict[str, float] | None
) -> None:
    active_keys = slot.environment_slot_keys
    existing = {row.environment_key: row for row in slot.environment_times}
    for key, row in list(existing.items()):
        if key not in active_keys:
            slot.environment_times.remove(row)
            del existing[key]
    for key in active_keys:
        value = None
        if provided and key in provided:
            value = max(0.0, float(provided[key]))
        row = existing.get(key)
        if row is not None:
            if value is not None:
                row.seconds = value
        else:
            slot.environment_times.append(
                EnvironmentTimeSeconds(environment_key=key, seconds=value or 0.0)
            )
    db.flush()


def patch_slot(db: Session, slot_id: int, patch_data: dict) -> SaveSlot:
    slot = get_slot(db, slot_id)
    slot.used = True

    env_time_update = patch_data.pop("environment_time_seconds", None)
    for field, value in patch_data.items():
        setattr(slot, field, value)

    if "environment_slot_keys" in patch_data or env_time_update is not None:
        _apply_environment_time_seconds(db, slot, env_time_update)

    total_visible_env_time = sum(row.seconds for row in slot.environment_times)
    if should_reveal_hidden_environment(
        total_visible_env_time, slot.hidden_cycle_index, slot.hidden_revealed
    ):
        slot.hidden_revealed = True
        slot.hidden_environment_name = generate_environment_for_slot(db, slot)
        slot.awaiting_hidden_relock_choice = True
        slot.current_tab = "environment"

    db.commit()
    db.refresh(slot)
    return slot

import json
import os

DEFAULT_SAVE_FILE_PATH = os.path.join("saves", "save_slots.json")
DEFAULT_ENVIRONMENT_KEYS = ["water", "earth", "air", "fire"]


def new_slot_state():
    return {
        "used": False,
        "current_tab": "stats",
        "time_alive_seconds": 0.0,
        "evolution_stage": "dormant",
        "evolution_click_progress": 0,
        "selected_environment": None,
        "environment_time_seconds": {
            "water": 0.0,
            "earth": 0.0,
            "air": 0.0,
            "fire": 0.0,
        },
        "hidden_revealed": False,
        "hidden_environment_name": None,
        "hidden_cycle_index": 1,
        "hidden_slot_index": 3,
        "environment_slot_keys": list(DEFAULT_ENVIRONMENT_KEYS),
        "awaiting_hidden_relock_choice": False,
    }


def load_save_slots(num_slots, save_file_path=DEFAULT_SAVE_FILE_PATH):
    default_slots = [new_slot_state() for _ in range(num_slots)]
    if not os.path.exists(save_file_path):
        return default_slots
    try:
        with open(save_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return default_slots
        slots = []
        for i in range(num_slots):
            candidate = data[i] if i < len(data) and isinstance(data[i], dict) else {}
            tab_value = candidate.get("current_tab")
            if tab_value == "path":
                tab_value = "environment"
            merged = new_slot_state()
            env_times = candidate.get("environment_time_seconds", {})
            if not isinstance(env_times, dict):
                env_times = {}
            sanitized_env_times = {}
            for k, v in env_times.items():
                key = str(k).lower()
                try:
                    sanitized_env_times[key] = max(0.0, float(v))
                except Exception:
                    continue
            selected_raw = candidate.get("selected_environment", None)
            if selected_raw is None:
                selected_environment = None
            else:
                selected_environment = str(selected_raw).lower()
            saved_evolution_stage = str(candidate.get("evolution_stage", "")).lower()
            if saved_evolution_stage not in {"dormant", "cracked", "hatching", "petawaru"}:
                # Backward compatibility for saves that used `monster_stage`.
                saved_monster_stage = candidate.get("monster_stage", None)
                if saved_monster_stage is not None:
                    saved_monster_stage = str(saved_monster_stage).lower()
                if saved_monster_stage == "petawaru":
                    saved_evolution_stage = "petawaru"
                elif saved_monster_stage == "cracked":
                    saved_evolution_stage = "cracked"
                else:
                    saved_evolution_stage = "dormant"

            merged.update({
                "used": bool(candidate.get("used", False)),
                "current_tab": "environment" if tab_value == "environment" else "stats",
                "time_alive_seconds": float(candidate.get("time_alive_seconds", 0.0)),
                "evolution_stage": saved_evolution_stage,
                "evolution_click_progress": int(candidate.get("evolution_click_progress", 0)),
                "selected_environment": selected_environment,
                "environment_time_seconds": sanitized_env_times,
                "hidden_revealed": bool(candidate.get("hidden_revealed", False)),
                "hidden_environment_name": candidate.get("hidden_environment_name", None),
                "hidden_cycle_index": int(candidate.get("hidden_cycle_index", 1)),
                "hidden_slot_index": int(candidate.get("hidden_slot_index", 3)),
                "environment_slot_keys": candidate.get("environment_slot_keys", DEFAULT_ENVIRONMENT_KEYS),
                "awaiting_hidden_relock_choice": bool(candidate.get("awaiting_hidden_relock_choice", False)),
            })
            if merged["hidden_cycle_index"] < 1:
                merged["hidden_cycle_index"] = 1
            if merged["hidden_slot_index"] not in (0, 1, 2, 3):
                merged["hidden_slot_index"] = 3
            keys = merged["environment_slot_keys"]
            if not isinstance(keys, list) or len(keys) != 4:
                merged["environment_slot_keys"] = list(DEFAULT_ENVIRONMENT_KEYS)
            else:
                norm_keys = [str(k).lower() for k in keys]
                merged["environment_slot_keys"] = [
                    "fire" if key == "hidden" else key
                    for key in norm_keys
                ]
            if len(set(merged["environment_slot_keys"])) != 4:
                deduped_keys = []
                for key in merged["environment_slot_keys"] + DEFAULT_ENVIRONMENT_KEYS:
                    if key and key not in deduped_keys:
                        deduped_keys.append(key)
                    if len(deduped_keys) == 4:
                        break
                merged["environment_slot_keys"] = deduped_keys
            if merged["evolution_stage"] not in {"dormant", "cracked", "hatching", "petawaru"}:
                merged["evolution_stage"] = "dormant"
            merged["evolution_click_progress"] = max(0, min(2, merged["evolution_click_progress"]))
            slots.append(merged)
        return slots
    except Exception:
        return default_slots


def write_save_slots(slots, save_file_path=DEFAULT_SAVE_FILE_PATH):
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    with open(save_file_path, "w", encoding="utf-8") as f:
        json.dump(slots, f, indent=2)

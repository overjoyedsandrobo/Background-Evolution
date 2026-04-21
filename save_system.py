import json
import os

DEFAULT_SAVE_FILE_PATH = os.path.join("saves", "save_slots.json")


def new_slot_state():
    return {
        "used": False,
        "current_tab": "stats",
        "time_alive_seconds": 0.0,
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
            merged.update({
                "used": bool(candidate.get("used", False)),
                "current_tab": "environment" if tab_value == "environment" else "stats",
                "time_alive_seconds": float(candidate.get("time_alive_seconds", 0.0)),
            })
            slots.append(merged)
        return slots
    except Exception:
        return default_slots


def write_save_slots(slots, save_file_path=DEFAULT_SAVE_FILE_PATH):
    os.makedirs(os.path.dirname(save_file_path), exist_ok=True)
    with open(save_file_path, "w", encoding="utf-8") as f:
        json.dump(slots, f, indent=2)

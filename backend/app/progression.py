"""Server-authoritative unlock/progression rules.

Ported from the client-side checks that used to live in main.py
(get_hidden_unlock_threshold_seconds / the total_visible_env_time check in
the event loop). The server now decides when a hidden environment is
revealed instead of the client.
"""

FIRST_CYCLE_THRESHOLD_SECONDS_TEST = 10.0


def get_hidden_unlock_threshold_seconds(cycle_index: int) -> float:
    return FIRST_CYCLE_THRESHOLD_SECONDS_TEST


def should_reveal_hidden_environment(
    total_visible_env_time: float, cycle_index: int, hidden_revealed: bool
) -> bool:
    if hidden_revealed:
        return False
    return total_visible_env_time >= get_hidden_unlock_threshold_seconds(cycle_index)

from app.progression import get_hidden_unlock_threshold_seconds, should_reveal_hidden_environment


def test_below_threshold_stays_locked():
    threshold = get_hidden_unlock_threshold_seconds(cycle_index=1)
    assert not should_reveal_hidden_environment(
        threshold - 0.01, cycle_index=1, hidden_revealed=False
    )


def test_at_or_above_threshold_reveals():
    threshold = get_hidden_unlock_threshold_seconds(cycle_index=1)
    assert should_reveal_hidden_environment(threshold, cycle_index=1, hidden_revealed=False)
    assert should_reveal_hidden_environment(threshold + 5.0, cycle_index=1, hidden_revealed=False)


def test_already_revealed_never_re_triggers():
    threshold = get_hidden_unlock_threshold_seconds(cycle_index=1)
    assert not should_reveal_hidden_environment(
        threshold + 100.0, cycle_index=1, hidden_revealed=True
    )

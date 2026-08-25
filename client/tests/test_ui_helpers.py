from ui_helpers import ShakeAnimation, format_time


def test_format_time_zero():
    assert format_time(0) == "00:00:00"


def test_format_time_under_a_minute():
    assert format_time(42) == "00:00:42"


def test_format_time_exact_minutes():
    assert format_time(120) == "00:02:00"


def test_format_time_hours():
    assert format_time(3725) == "01:02:05"


def test_format_time_ignores_fractional_seconds():
    assert format_time(59.9) == "00:00:59"


def test_shake_animation_starts_inactive():
    shake = ShakeAnimation()
    assert shake.active is False
    assert shake.get_offset() == 0


def test_shake_animation_trigger_activates():
    shake = ShakeAnimation(duration=0.15)
    shake.trigger()
    assert shake.active is True
    assert shake.timer == 0.0


def test_shake_animation_deactivates_after_duration():
    shake = ShakeAnimation(duration=0.1)
    shake.trigger()
    shake.update(0.05)
    assert shake.active is True
    shake.update(0.1)
    assert shake.active is False


def test_shake_animation_offset_is_bounded_by_magnitude():
    shake = ShakeAnimation(duration=1.0, magnitude=5)
    shake.trigger()
    shake.update(0.01)
    assert abs(shake.get_offset()) <= 5

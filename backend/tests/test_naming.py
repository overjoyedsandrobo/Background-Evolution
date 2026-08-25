import random

from app.game_engine.naming import (
    ELEMENT_WORDS,
    EMERGENT_QUALIFIERS,
    compose_name,
)
from app.game_engine.prototypes import ALL_TRAITS


def _traits(**overrides):
    t = {k: 0.0 for k in ALL_TRAITS}
    t.update(overrides)
    return t


def test_pure_dominant_name_uses_only_dominant_word_bank():
    random.seed(0)
    weights = {"fire": 0.9, "water": 0.03, "earth": 0.03, "air": 0.04}
    for _ in range(20):
        name = compose_name(weights, _traits(), tier=1.0)
        assert any(word in name for word in ELEMENT_WORDS["fire"])


def test_hybrid_name_combines_top_two_elements():
    random.seed(0)
    weights = {"fire": 0.45, "water": 0.4, "earth": 0.1, "air": 0.05}
    for _ in range(20):
        name = compose_name(weights, _traits(), tier=1.0)
        assert any(word in name for word in ELEMENT_WORDS["fire"]) or any(
            word in name for word in ELEMENT_WORDS["water"]
        )


def test_tier_one_has_no_epithet():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(), tier=1.0)
    assert not name.startswith(("Greater", "Grand", "Ascendant", "Primordial", "Celestial"))


def test_higher_tier_adds_an_escalating_epithet():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(), tier=3.0)
    assert name.startswith("Grand ")


def test_tier_beyond_ladder_appends_numeral_suffix():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(), tier=9.0)
    assert "II" in name or "III" in name or name.split()[-1].isupper()


def test_emergent_trait_over_threshold_adds_qualifier():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(corruption=0.9), tier=1.0)
    assert EMERGENT_QUALIFIERS["corruption"] in name


def test_no_emergent_qualifier_below_threshold():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    for qualifier in EMERGENT_QUALIFIERS.values():
        name = compose_name(weights, _traits(), tier=1.0)
        assert qualifier not in name

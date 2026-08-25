import random

from app.game_engine.naming import (
    COSMIC_TEMPLATES,
    EMERGENT_QUALIFIERS,
    VOCAB,
    _band_for_tier,
    compose_name,
    words_for_element,
)
from app.game_engine.prototypes import ALL_TRAITS


def _traits(**overrides):
    t = {k: 0.0 for k in ALL_TRAITS}
    t.update(overrides)
    return t


def test_band_boundaries():
    assert _band_for_tier(1.0) == "grounded"
    assert _band_for_tier(2.9) == "grounded"
    assert _band_for_tier(3.0) == "wild"
    assert _band_for_tier(4.9) == "wild"
    assert _band_for_tier(5.0) == "elemental"
    assert _band_for_tier(6.9) == "elemental"
    assert _band_for_tier(7.0) == "mythic"
    assert _band_for_tier(8.9) == "mythic"
    assert _band_for_tier(9.0) == "celestial"
    assert _band_for_tier(10.9) == "celestial"
    assert _band_for_tier(11.0) == "cosmic"
    assert _band_for_tier(50.0) == "cosmic"


def test_pure_dominant_name_uses_only_dominant_noun_bank():
    random.seed(0)
    weights = {"fire": 0.9, "water": 0.03, "earth": 0.03, "air": 0.04}
    for _ in range(20):
        name = compose_name(weights, _traits(), tier=1.0)
        assert name in VOCAB["grounded"]["fire"]["noun"]


def test_hybrid_name_is_secondary_adjective_plus_dominant_noun():
    random.seed(0)
    weights = {"fire": 0.45, "water": 0.4, "earth": 0.1, "air": 0.05}
    for _ in range(20):
        name = compose_name(weights, _traits(), tier=1.0)
        adjective, _, noun = name.partition(" ")
        assert adjective in VOCAB["grounded"]["water"]["adj"]
        assert noun in VOCAB["grounded"]["fire"]["noun"]


def test_grounded_tier_uses_realistic_biome_vocabulary():
    random.seed(0)
    weights = {"earth": 1.0, "fire": 0.0, "water": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(), tier=1.0)
    assert name in VOCAB["grounded"]["earth"]["noun"]


def test_higher_bands_use_progressively_different_vocabulary():
    random.seed(0)
    weights = {"earth": 1.0, "fire": 0.0, "water": 0.0, "air": 0.0}
    seen_bands = set()
    for tier, expected_band in [
        (1.0, "grounded"),
        (3.0, "wild"),
        (7.0, "mythic"),
        (9.0, "celestial"),
    ]:
        name = compose_name(weights, _traits(), tier=tier)
        assert name in VOCAB[expected_band]["earth"]["noun"]
        seen_bands.add(name)
    # every band produced a distinct vocabulary set (no overlap by design)
    assert len(seen_bands) == 4


def test_cosmic_band_uses_poetic_templates_not_noun_grammar():
    random.seed(0)
    weights = {"water": 1.0, "fire": 0.0, "earth": 0.0, "air": 0.0}
    for _ in range(10):
        name = compose_name(weights, _traits(), tier=11.0)
        assert name in COSMIC_TEMPLATES["water"]


def test_emergent_trait_over_threshold_adds_qualifier_prefix():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    name = compose_name(weights, _traits(corruption=0.9), tier=1.0)
    assert name.startswith(EMERGENT_QUALIFIERS["corruption"])


def test_no_emergent_qualifier_below_threshold():
    random.seed(1)
    weights = {"fire": 1.0, "water": 0.0, "earth": 0.0, "air": 0.0}
    for qualifier in EMERGENT_QUALIFIERS.values():
        name = compose_name(weights, _traits(), tier=1.0)
        assert not name.startswith(qualifier)


def test_words_for_element_covers_every_band():
    fire_words = words_for_element("fire")
    for band in VOCAB.values():
        assert set(band["fire"]["noun"]) <= fire_words
        assert set(band["fire"]["adj"]) <= fire_words


def test_compose_name_avoids_collisions_with_existing_names():
    random.seed(0)
    weights = {"fire": 0.9, "water": 0.03, "earth": 0.04, "air": 0.03}
    existing = set(VOCAB["grounded"]["fire"]["noun"])  # exhaust the whole bank
    for _ in range(10):
        name = compose_name(weights, _traits(), tier=1.0, existing_names=existing)
        assert name not in existing


def test_compose_name_falls_back_to_numeral_suffix_when_bank_is_exhausted():
    random.seed(0)
    weights = {"fire": 0.9, "water": 0.03, "earth": 0.04, "air": 0.03}
    all_nouns = VOCAB["grounded"]["fire"]["noun"]
    existing = set(all_nouns)  # every pure-mode name this combo could produce
    name = compose_name(weights, _traits(), tier=1.0, existing_names=existing)
    assert name not in existing
    assert any(name == f"{noun} II" for noun in all_nouns)


def test_compose_name_with_no_existing_names_behaves_as_before():
    random.seed(0)
    weights = {"fire": 0.9, "water": 0.03, "earth": 0.04, "air": 0.03}
    name = compose_name(weights, _traits(), tier=1.0)
    assert name in VOCAB["grounded"]["fire"]["noun"]

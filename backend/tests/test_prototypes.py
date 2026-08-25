from app.game_engine.prototypes import ALL_TRAITS


def test_all_traits_non_empty_and_unique():
    assert len(ALL_TRAITS) == len(set(ALL_TRAITS))
    assert len(ALL_TRAITS) > 0


def test_emergent_traits_present():
    assert {"arcane", "resonance", "corruption", "sanctity"} <= set(ALL_TRAITS)

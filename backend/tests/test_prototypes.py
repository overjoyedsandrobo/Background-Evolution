from app.game_engine.prototypes import ALL_TRAITS, PROTOTYPE_LIBRARY


def test_every_prototype_has_all_trait_keys():
    for proto in PROTOTYPE_LIBRARY:
        assert set(proto["traits"].keys()) == set(ALL_TRAITS)


def test_no_duplicate_prototype_names():
    names = [p["name"] for p in PROTOTYPE_LIBRARY]
    assert len(names) == len(set(names))


def test_gen_affinity_is_non_negative():
    for proto in PROTOTYPE_LIBRARY:
        assert proto["gen_affinity"] >= 0

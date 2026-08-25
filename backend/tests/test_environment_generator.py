import math
import random

import pytest

from app.game_engine.environment_generator import (
    BASE_ENVIRONMENTS,
    World,
    _compute_child_tier,
    generate_next_environment,
)


def test_base_environments_have_zero_tier():
    for env in BASE_ENVIRONMENTS.values():
        assert env.tier == 0.0


def test_child_tier_is_one_plus_weighted_average_of_parent_tiers():
    # 1 + (0.5*0 + 0.5*4) = 3.0
    assert _compute_child_tier([0.0, 4.0], [0.5, 0.5]) == pytest.approx(3.0)


def test_first_generation_child_has_tier_one():
    world = World()
    parents = [world.get(n) for n in ["air", "earth", "water", "fire"]]
    env = generate_next_environment(parents, [0.25, 0.25, 0.25, 0.25])
    assert env.tier == pytest.approx(1.0)


def test_leaning_into_a_high_tier_lineage_compounds_tier():
    random.seed(0)
    world = World()
    dominant = world.get("fire")
    others = [world.get("air"), world.get("earth"), world.get("water")]
    tiers = [dominant.tier]
    for _ in range(5):
        parents = [dominant, *others]
        # heavy dominance on the climbing lineage each round
        dominant = generate_next_environment(parents, [0.85, 0.05, 0.05, 0.05])
        tiers.append(dominant.tier)
    assert tiers == sorted(tiers)
    assert tiers[-1] > tiers[0] + 3


def test_even_split_across_base_elements_grows_tier_slowly():
    random.seed(0)
    world = World()
    env = world.get("air")
    for _ in range(3):
        parents = [env, world.get("earth"), world.get("water"), world.get("fire")]
        env = generate_next_environment(parents, [0.25, 0.25, 0.25, 0.25])
    assert env.tier < 3.0


def test_deterministic_with_seed():
    parents_names = ["air", "earth", "water", "fire"]
    ratios = [0.25, 0.25, 0.25, 0.25]

    random.seed(7)
    world_a = World()
    parents_a = [world_a.get(n) for n in parents_names]
    env_a = generate_next_environment(parents_a, ratios)

    random.seed(7)
    world_b = World()
    parents_b = [world_b.get(n) for n in parents_names]
    env_b = generate_next_environment(parents_b, ratios)

    assert env_a.name == env_b.name
    assert env_a.traits == env_b.traits


def test_requires_exactly_four_parents():
    world = World()
    parents = [world.get("fire")] * 3
    with pytest.raises(ValueError):
        generate_next_environment(parents, [0.33, 0.33, 0.34])


def test_rejects_all_zero_ratios():
    world = World()
    parents = [world.get(n) for n in ["air", "earth", "water", "fire"]]
    with pytest.raises(ValueError):
        generate_next_environment(parents, [0.0, 0.0, 0.0, 0.0])


def test_world_generate_registers_child_by_name():
    random.seed(1)
    world = World()
    env = world.generate(["fire", "fire", "fire", "fire"], [0.25] * 4)
    assert world.environments[env.name] is env


def test_generated_traits_stay_within_bounds():
    random.seed(3)
    world = World()
    env = world.get("fire")
    for _ in range(8):
        parents = [env, world.get("fire"), world.get("earth"), world.get("air")]
        env = generate_next_environment(parents, [0.7, 0.1, 0.1, 0.1])
        assert all(0.0 <= v <= 1.0 for v in env.traits.values())
        assert not any(math.isnan(v) for v in env.traits.values())

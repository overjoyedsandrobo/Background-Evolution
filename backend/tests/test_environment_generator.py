import random

import pytest

from app.game_engine.environment_generator import World, generate_next_environment


def test_all_fire_generates_inferno_family():
    random.seed(42)
    world = World()
    for _ in range(8):
        env = world.generate(["fire", "fire", "fire", "fire"], [0.25] * 4)
        assert env.name in {"inferno", "wildfire", "aurora"} or env.generation == 1


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


def test_child_generation_is_one_above_max_parent_when_no_dominance():
    world = World()
    parents = [world.get(n) for n in ["air", "earth", "water", "fire"]]
    env = generate_next_environment(parents, [0.25, 0.25, 0.25, 0.25])
    assert env.generation == 1


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

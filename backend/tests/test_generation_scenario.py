"""End-to-end scenario test: repeatedly combine 4 active environments, swap
a random slot for the freshly generated one, and repeat - so later steps
combine base environments with already-generated (and increasingly
higher-tier) ones, same as real play. Sanity-checks that every result is
internally consistent (bounded traits/weights, tier can only grow, the name
actually reflects what went into it) and prints a readable trace (run with
`pytest -s` to see it) so the naming/tier progression can be eyeballed for
whether it "feels" right.
"""

import random

import pytest

from app.game_engine.environment_generator import World
from app.game_engine.naming import ELEMENT_WORDS

BASE_KEYS = ["air", "earth", "water", "fire"]
STEPS = 10


def _random_ratios(n=4):
    raw = [random.random() + 0.01 for _ in range(n)]
    total = sum(raw)
    return [r / total for r in raw]


def _name_reflects_composition(name: str, weights: dict[str, float]) -> bool:
    full_weights = {el: weights.get(el, 0.0) for el in ELEMENT_WORDS}
    ordered = sorted(full_weights.items(), key=lambda kv: kv[1], reverse=True)
    dominant, second = ordered[0][0], ordered[1][0]
    candidates = ELEMENT_WORDS[dominant] + ELEMENT_WORDS[second]
    return any(word in name for word in candidates)


@pytest.mark.parametrize("seed", range(5))
def test_ten_step_generation_chain_is_internally_consistent(seed):
    random.seed(seed)
    world = World()
    active = list(BASE_KEYS)
    trace = [f"\n=== generation chain, seed={seed} ==="]
    last_tier = 0.0

    for step in range(1, STEPS + 1):
        ratios = _random_ratios()
        child = world.generate(active, ratios)

        assert child.name
        assert child.tier >= 1.0 - 1e-9
        assert abs(sum(child.weights.values()) - 1.0) < 1e-6
        assert all(0.0 <= v <= 1.0 for v in child.weights.values())
        assert all(0.0 <= v <= 1.0 for v in child.traits.values())
        assert _name_reflects_composition(child.name, child.weights), (
            f"{child.name!r} doesn't reflect its composition {child.weights}"
        )

        replace_idx = random.randrange(4)
        parents_desc = ", ".join(
            f"{name}({ratio:.2f})" for name, ratio in zip(active, ratios, strict=False)
        )
        dominant_traits = sorted(child.traits.items(), key=lambda kv: kv[1], reverse=True)[:3]
        traits_desc = ", ".join(f"{k}={v:.2f}" for k, v in dominant_traits)
        trace.append(
            f"step {step:2d}: [{parents_desc}] "
            f"-> {child.name!r} tier={child.tier:.2f} top_traits=({traits_desc}) "
            f"| replacing slot {replace_idx} ({active[replace_idx]!r})"
        )
        active[replace_idx] = child.name
        last_tier = child.tier

    trace.append(f"final active set: {active}, last tier: {last_tier:.2f}")
    print("\n".join(trace))

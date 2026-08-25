"""Environment Generator — 4-Base Procedural System (Runtime)
================================================================
The 4 base environments (air, earth, water, fire) are hardcoded roots.
Everything generated from combining them — weights, traits, tier, and name
— is computed continuously from the parents' own weights/traits/tier and
the ratio they were combined in. See
docs/design/procedural-environment-generation.md for the design.

Usage:
    from app.game_engine.environment_generator import World

    world = World()
    # Generate from 4 parents (can use same parent multiple times)
    env = world.generate(["air", "earth", "water", "fire"], [0.4, 0.3, 0.2, 0.1])
    print(env.name, env.tier)
"""

import random
from dataclasses import dataclass

from app.game_engine import naming
from app.game_engine.prototypes import ALL_TRAITS

# Constants
N_TRAITS = len(ALL_TRAITS)
EMERGENT = {"arcane", "resonance", "corruption", "sanctity"}

BASE_TRAIT_SIGMA = 0.06
AMPLIFICATION_FACTOR = 0.20
EMERGENT_DRIFT_SIGMA = 0.012
GROWTH_CAP = 1.0


@dataclass
class Environment:
    name: str
    weights: dict[str, float]
    traits: dict[str, float]
    tier: float
    parents: list[str]

    def trait_vec(self) -> list[float]:
        return [self.traits.get(t, 0.0) for t in ALL_TRAITS]


def _ft(**kw):
    t = {k: 0.0 for k in ALL_TRAITS}
    t.update(kw)
    return t


_BASE_TRAIT_DEFS = {
    "air": _ft(
        temperature=0.40,
        pressure=0.00,
        gravity=0.00,
        solidity=0.00,
        humidity=0.00,
        toxicity=0.00,
        windspeed=1.00,
        visibility=1.00,
        luminosity=1.00,
        radiation=0.05,
        magnetism=0.00,
        volatility=1.00,
        flora=0.00,
        fauna=0.00,
        decay=0.00,
        age=0.00,
    ),
    "earth": _ft(
        temperature=0.60,
        pressure=1.00,
        gravity=1.00,
        solidity=1.00,
        humidity=0.05,
        toxicity=0.35,
        windspeed=0.00,
        visibility=0.00,
        luminosity=0.00,
        radiation=0.40,
        magnetism=0.60,
        volatility=0.00,
        flora=0.00,
        fauna=0.00,
        decay=0.00,
        age=1.00,
    ),
    "water": _ft(
        temperature=0.15,
        pressure=0.70,
        gravity=0.60,
        solidity=0.02,
        humidity=1.00,
        toxicity=0.20,
        windspeed=0.05,
        visibility=0.10,
        luminosity=0.05,
        radiation=0.00,
        magnetism=0.05,
        volatility=0.10,
        flora=1.00,
        fauna=1.00,
        decay=0.80,
        age=0.75,
    ),
    "fire": _ft(
        temperature=1.00,
        pressure=0.30,
        gravity=0.10,
        solidity=0.00,
        humidity=0.00,
        toxicity=0.70,
        windspeed=0.60,
        visibility=0.20,
        luminosity=0.95,
        radiation=0.85,
        magnetism=0.05,
        volatility=1.00,
        flora=0.00,
        fauna=0.00,
        decay=0.00,
        age=0.00,
    ),
}

BASE_ENVIRONMENTS = {
    name: Environment(name=name, weights={name: 1.0}, traits=traits, tier=0.0, parents=[])
    for name, traits in _BASE_TRAIT_DEFS.items()
}


def _normalize(d):
    total = sum(d.values())
    return {k: v / total for k, v in d.items()} if total else {k: 1.0 / len(d) for k in d}


def _clamp01(d):
    return {k: max(0.0, min(1.0, v)) for k, v in d.items()}


def _growth(tier: float) -> float:
    return max(0.0, min(GROWTH_CAP, tier - 1.0))


def _compute_child_tier(parent_tiers, ratios):
    return 1.0 + sum(r * t for r, t in zip(ratios, parent_tiers, strict=False))


def _blend_traits(parent_traits, ratios, tier):
    means = {
        t: sum(pt.get(t, 0) * r for pt, r in zip(parent_traits, ratios, strict=False))
        for t in ALL_TRAITS
    }

    dominance = max(ratios)
    sigma_scale = max(0.0, min(1.0, 1.0 - ((dominance - 0.25) / 0.75)))
    growth = _growth(tier)
    effective_sig = BASE_TRAIT_SIGMA * sigma_scale * growth
    effective_amplification = AMPLIFICATION_FACTOR * growth

    variances = {
        t: sum(
            r * (pt.get(t, 0) - means[t]) ** 2 for pt, r in zip(parent_traits, ratios, strict=False)
        )
        for t in ALL_TRAITS
    }

    blended = {}
    for t in ALL_TRAITS:
        mean = means[t]
        agreement = 1.0 - min(variances[t] / 0.25, 1.0)
        extreme = 1.0 if mean >= 0.5 else 0.0
        amplified = mean + agreement * (extreme - mean) * effective_amplification
        noisy = amplified + random.gauss(0, effective_sig)
        if t in EMERGENT:
            noisy += abs(random.gauss(0, EMERGENT_DRIFT_SIGMA * tier))
        blended[t] = noisy

    return _clamp01(blended)


def _blend_weights(parent_weights, ratios, dominance, tier):
    merged = {}
    for pw, r in zip(parent_weights, ratios, strict=False):
        for k, v in pw.items():
            merged[k] = merged.get(k, 0.0) + v * r

    growth = _growth(tier)
    w_sigma = max(0.0, 0.04 * (1.0 - ((dominance - 0.25) / 0.75))) * growth
    noisy = {k: max(0.0, v + random.gauss(0, w_sigma)) for k, v in merged.items()}
    noisy = {k: v for k, v in noisy.items() if v > 1e-4}
    return _normalize(noisy)


def generate_next_environment(parents, time_ratios=None):
    if len(parents) != 4:
        raise ValueError("Exactly 4 parents required.")
    if time_ratios is None:
        time_ratios = [0.25, 0.25, 0.25, 0.25]
    if len(time_ratios) != 4:
        raise ValueError("time_ratios must have 4 values.")
    if any(r < 0 for r in time_ratios):
        raise ValueError("time_ratios must be non-negative.")

    total = sum(time_ratios)
    if total == 0:
        raise ValueError("At least one ratio must be > 0.")

    ratios = [r / total for r in time_ratios]
    dominance = max(ratios)
    child_tier = _compute_child_tier([p.tier for p in parents], ratios)

    final_weights = _blend_weights([p.weights for p in parents], ratios, dominance, child_tier)
    final_traits = _blend_traits([p.traits for p in parents], ratios, child_tier)
    chosen_name = naming.compose_name(final_weights, final_traits, child_tier)

    return Environment(
        name=chosen_name,
        weights=final_weights,
        traits=final_traits,
        tier=child_tier,
        parents=[p.name for p in parents],
    )


class World:
    def __init__(self):
        self.environments = dict(BASE_ENVIRONMENTS)

    def get(self, name):
        if name not in self.environments:
            raise KeyError(f"Environment '{name}' not found.")
        return self.environments[name]

    def add(self, env):
        # Store without suffix - just overwrite if it already exists
        self.environments[env.name] = env
        return env

    def generate(self, parent_names, time_ratios=None):
        parents = [self.get(n) for n in parent_names]
        child = generate_next_environment(parents, time_ratios)
        return self.add(child)


if __name__ == "__main__":
    random.seed(42)
    world = World()

    print("4-BASE PROCEDURAL ENVIRONMENT GENERATOR")
    print("=" * 70)
    print()

    tests = [
        (["air", "air", "air", "air"], [0.25] * 4, "100% air"),
        (["earth", "earth", "earth", "earth"], [0.25] * 4, "100% earth"),
        (["water", "water", "water", "water"], [0.25] * 4, "100% water"),
        (["fire", "fire", "fire", "fire"], [0.25] * 4, "100% fire"),
        (["air", "water", "water", "water"], [0.25] * 4, "air+water"),
        (["earth", "fire", "fire", "fire"], [0.25] * 4, "earth+fire"),
        (["air", "earth", "water", "fire"], [0.25] * 4, "balanced quarters"),
    ]

    for parents, ratios, label in tests:
        results = [world.generate(parents, ratios) for _ in range(4)]
        print(f"{label:20s}: {[(e.name, round(e.tier, 2)) for e in results]}")

    print()
    print("Leaning on a lineage compounds tier toward grander results over time.")

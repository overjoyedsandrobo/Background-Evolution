"""
Environment Generator v4 — 4-Base System (Runtime)
===================================================
Complete runtime with 75 environments (15 per tier × 5 tiers).

Usage:
    from environment_generator_v4_full import World

    world = World()
    # Generate from 4 parents (can use same parent multiple times)
    env = world.generate(["air", "earth", "water", "fire"], [0.4, 0.3, 0.2, 0.1])
    print(env.name, env.generation)
"""

import math
import random
from dataclasses import dataclass

from prototypes_v4_fitted import ALL_TRAITS, PROTO_GENS, PROTO_VECS, PROTOTYPE_LIBRARY

# Constants
N_TRAITS = len(ALL_TRAITS)
EMERGENT = {"arcane", "resonance", "corruption", "sanctity"}

BASE_TRAIT_SIGMA = 0.06
AMPLIFICATION_FACTOR = 0.20
EMERGENT_DRIFT_SIGMA = 0.012
GEN_BIAS_STRENGTH = 0.30
SOFTMAX_TEMPERATURE = 0.05


@dataclass
class Environment:
    name: str
    weights: dict[str, float]
    traits: dict[str, float]
    generation: int
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
    name: Environment(name=name, weights={name: 1.0}, traits=traits, generation=0, parents=[])
    for name, traits in _BASE_TRAIT_DEFS.items()
}


def _normalize(d):
    total = sum(d.values())
    return {k: v / total for k, v in d.items()} if total else {k: 1.0 / len(d) for k in d}


def _clamp01(d):
    return {k: max(0.0, min(1.0, v)) for k, v in d.items()}


def _cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    ma = math.sqrt(sum(x * x for x in a))
    mb = math.sqrt(sum(x * x for x in b))
    return dot / (ma * mb) if ma and mb else 0.0


def _euclidean_dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=False)))


def _softmax(scores, temp=SOFTMAX_TEMPERATURE):
    scaled = [s / max(temp, 1e-9) for s in scores]
    max_s = max(scaled)
    exps = [math.exp(s - max_s) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def _compute_child_gen(parent_gens, ratios):
    max_gen = max(parent_gens)
    dom_idx = max(range(len(ratios)), key=lambda i: ratios[i])
    dom_gen = parent_gens[dom_idx]
    dom_ratio = ratios[dom_idx]
    if dom_ratio > 0.50 and dom_gen < max_gen:
        return dom_gen + 1
    return max_gen + 1


def _blend_traits(parent_traits, ratios, child_gen):
    means = {
        t: sum(pt.get(t, 0) * r for pt, r in zip(parent_traits, ratios, strict=False))
        for t in ALL_TRAITS
    }

    # For gen-1, use deterministic blending (no noise) to match fitted prototypes
    if child_gen == 1:
        return _clamp01(means)

    # For gen-2+, add noise and drift
    dominance = max(ratios)
    sigma_scale = max(0.0, min(1.0, 1.0 - ((dominance - 0.25) / 0.75)))
    effective_sig = BASE_TRAIT_SIGMA * sigma_scale

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
        amplified = mean + agreement * (extreme - mean) * AMPLIFICATION_FACTOR
        noisy = amplified + random.gauss(0, effective_sig)
        if t in EMERGENT and child_gen > 0:
            noisy += abs(random.gauss(0, EMERGENT_DRIFT_SIGMA * child_gen))
        blended[t] = noisy

    return _clamp01(blended)


def _blend_weights(parent_weights, ratios, dominance, child_gen):
    merged = {}
    for pw, r in zip(parent_weights, ratios, strict=False):
        for k, v in pw.items():
            merged[k] = merged.get(k, 0.0) + v * r

    # Gen-1: deterministic (no noise)
    if child_gen == 1:
        return _normalize(merged)

    # Gen-2+: add noise for variety
    w_sigma = max(0.0, 0.04 * (1.0 - ((dominance - 0.25) / 0.75)))
    noisy = {k: max(0.0, v + random.gauss(0, w_sigma)) for k, v in merged.items()}
    noisy = {k: v for k, v in noisy.items() if v > 1e-4}
    return _normalize(noisy)


def _name_from_library(trait_vec, child_gen):
    scores = []
    for pvec, pg in zip(PROTO_VECS, PROTO_GENS, strict=False):
        # STRICT: gen-0/1 blends can ONLY name as their exact generation.
        # No gen-2 names from gen-1 blends, ever.
        if child_gen <= 1 and pg != child_gen:
            scores.append(-999.0)
            continue
        # For gen-2+, allow ±1 generation flexibility
        if child_gen > 1 and abs(child_gen - pg) > 1:
            scores.append(-999.0)
            continue
        sim = _cosine_sim(trait_vec, pvec)
        dist = _euclidean_dist(trait_vec, pvec)
        euc_pen = dist / 4.47
        score = (0.7 * sim - 0.3 * euc_pen) - GEN_BIAS_STRENGTH * abs(child_gen - pg)
        scores.append(score)
    # Gen-1: very tight softmax (temp 0.02) for variety on non-recipes
    # Gen-2+: looser softmax (temp 0.05) for more variety
    if child_gen == 1:
        # Use much tighter temperature for gen-1
        probs = _softmax(scores, temp=0.01)
    else:
        probs = _softmax(scores, temp=SOFTMAX_TEMPERATURE)

    chosen = random.choices(PROTOTYPE_LIBRARY, weights=probs, k=1)[0]
    return chosen["name"]


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
    child_gen = _compute_child_gen([p.generation for p in parents], ratios)

    final_weights = _blend_weights([p.weights for p in parents], ratios, dominance, child_gen)
    final_traits = _blend_traits([p.traits for p in parents], ratios, child_gen)
    trait_vec = [final_traits.get(t, 0.0) for t in ALL_TRAITS]
    chosen_name = _name_from_library(trait_vec, child_gen)

    return Environment(
        name=chosen_name,
        weights=final_weights,
        traits=final_traits,
        generation=child_gen,
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

    print("4-BASE ENVIRONMENT GENERATOR")
    print("=" * 70)
    print()

    print("Testing base combinations (8 runs each):")
    print()

    tests = [
        (["air", "air", "air", "air"], [0.25] * 4, "100% air → sky"),
        (["earth", "earth", "earth", "earth"], [0.25] * 4, "100% earth → cave"),
        (["water", "water", "water", "water"], [0.25] * 4, "100% water → ocean"),
        (["fire", "fire", "fire", "fire"], [0.25] * 4, "100% fire → inferno"),
        (["air", "water", "water", "water"], [0.25] * 4, "air+water → storm/reef"),
        (["earth", "fire", "fire", "fire"], [0.25] * 4, "earth+fire → volcano/mine"),
        (["air", "earth", "water", "fire"], [0.25] * 4, "balanced quarters"),
    ]

    for parents, ratios, label in tests:
        results = [world.generate(parents, ratios).name for _ in range(8)]
        clean = [n.rsplit("_", 1)[0] if n.rsplit("_", 1)[-1].isdigit() else n for n in results]
        print(f"{label:30s}: {clean}")

    print()
    print("System ready. 75 environments available across 5 generations.")

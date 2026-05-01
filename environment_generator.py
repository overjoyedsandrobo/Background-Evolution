"""
Environment Generator — v3 (Runtime)
======================================
Fully integrated with ML-fitted recipes from ml_fitting.py.

Architecture:
  - 4 base environments (air, earth, water, fire) at generation 0
  - 50 named environments across 5 generations, each with a fitted recipe
  - generate_next_environment() blends 3 parents by time ratios
  - Naming: gen <= 5 -> softmax over prototype library; gen > 5 -> Claude API
  - World registry tracks all environments ever created
  - Recipe lookup: given a target name, returns the canonical parent recipe

Key design decisions:
  - Ratio dominance scaling: noise shrinks when one parent dominates
  - Agreement amplification: consensus traits push toward extremes
  - Metaphysical traits drift upward each generation
  - Generation math: max(parent_gens)+1, dominant gen-0 parent can pull back
"""

from __future__ import annotations

import json
import math
import os
import random
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Trait system
# ---------------------------------------------------------------------------

PHYSICALITY  = ["temperature", "pressure", "gravity", "solidity"]
ATMOSPHERE   = ["humidity", "toxicity", "windspeed", "visibility"]
ENERGY       = ["luminosity", "radiation", "magnetism", "volatility"]
LIFE         = ["flora", "fauna", "decay", "age"]
METAPHYSICAL = ["arcane", "resonance", "corruption", "sanctity"]

ALL_TRAITS = PHYSICALITY + ATMOSPHERE + ENERGY + LIFE + METAPHYSICAL
EMERGENT   = set(METAPHYSICAL)
N_TRAITS   = len(ALL_TRAITS)
TRAIT_IDX  = {t: i for i, t in enumerate(ALL_TRAITS)}

BASE_TRAIT_SIGMA     = 0.06
AMPLIFICATION_FACTOR = 0.20
EMERGENT_DRIFT_SIGMA = 0.012
GEN_BIAS_STRENGTH    = 0.30
SOFTMAX_TEMPERATURE  = 0.15
API_GEN_THRESHOLD    = 5


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class Environment:
    name:       str
    weights:    dict[str, float]
    traits:     dict[str, float]
    generation: int
    parents:    list[str]

    def trait_vec(self) -> list[float]:
        return [self.traits.get(t, 0.0) for t in ALL_TRAITS]

    def trait_summary(self, threshold: float = 0.15) -> str:
        notable = [(k, v) for k, v in self.traits.items() if v > threshold]
        notable.sort(key=lambda x: -x[1])
        return ", ".join(f"{k}={v:.2f}" for k, v in notable[:8])

    def __repr__(self) -> str:
        top_w = sorted(self.weights.items(), key=lambda x: -x[1])[:3]
        w_str = ", ".join(f"{k}:{v:.2f}" for k, v in top_w)
        return (
            f"Environment(name={self.name!r}, gen={self.generation}, "
            f"parents={self.parents})\n"
            f"  weights : {w_str}\n"
            f"  traits  : {self.trait_summary()}"
        )


# ---------------------------------------------------------------------------
# Base environments
# ---------------------------------------------------------------------------

def _ft(**kw) -> dict[str, float]:
    t = {k: 0.0 for k in ALL_TRAITS}
    t.update(kw)
    return t


_BASE_TRAIT_DEFS = {
    "air": _ft(
        temperature=0.45, pressure=0.02, gravity=0.02, solidity=0.00,
        humidity=0.02,    toxicity=0.00, windspeed=0.99, visibility=0.99,
        luminosity=0.99,  radiation=0.10, magnetism=0.02, volatility=0.99,
        flora=0.00,       fauna=0.02,    decay=0.00,    age=0.00,
    ),
    "earth": _ft(
        # Geothermal underground: hot core, crushing, pitch black, ancient, minimal life
        temperature=0.99, pressure=0.99, gravity=0.99, solidity=0.99,
        humidity=0.02,    toxicity=0.40, windspeed=0.00, visibility=0.00,
        luminosity=0.00,  radiation=0.40, magnetism=0.50, volatility=0.02,
        flora=0.05,       fauna=0.05,    decay=0.30,    age=0.99,
    ),
    "water": _ft(
        # Life-source: teeming, toxic, decaying, lush — origin of all biological life
        temperature=0.00, pressure=0.75, gravity=0.65, solidity=0.02,
        humidity=0.99,    toxicity=0.55, windspeed=0.05, visibility=0.02,
        luminosity=0.02,  radiation=0.02, magnetism=0.05, volatility=0.15,
        flora=0.99,       fauna=0.80,    decay=0.75,    age=0.80,
    ),
    "fire": _ft(
        temperature=0.99, pressure=0.35, gravity=0.12, solidity=0.00,
        humidity=0.00,    toxicity=0.25, windspeed=0.55, visibility=0.72,
        luminosity=0.99,  radiation=0.35, magnetism=0.04, volatility=0.98,
        flora=0.00,       fauna=0.02,    decay=0.62,    age=0.05,
    ),
}

BASE_ENVIRONMENTS: dict[str, Environment] = {
    name: Environment(name=name, weights={name: 1.0}, traits=traits,
                      generation=0, parents=[])
    for name, traits in _BASE_TRAIT_DEFS.items()
}


# ---------------------------------------------------------------------------
# Prototype library
# ---------------------------------------------------------------------------

def _proto(name: str, gen_affinity: float, **traits) -> dict:
    t = {k: 0.0 for k in ALL_TRAITS}
    t.update(traits)
    return {"name": name, "gen_affinity": gen_affinity, "traits": t}


PROTOTYPE_LIBRARY: list[dict] = [
    # Gen 1
    _proto("storm",   1,
           temperature=0.25, pressure=0.85, gravity=0.50, solidity=0.00,
           humidity=0.92, toxicity=0.02, windspeed=0.99, visibility=0.05,
           luminosity=0.05, radiation=0.05, magnetism=0.05, volatility=0.99,
           flora=0.00, fauna=0.00, decay=0.00, age=0.02),
    _proto("cave",    1,
           temperature=0.45, pressure=0.99, gravity=0.98, solidity=0.99,
           humidity=0.45, toxicity=0.08, windspeed=0.00, visibility=0.00,
           luminosity=0.00, radiation=0.08, magnetism=0.25, volatility=0.00,
           flora=0.02, fauna=0.05, decay=0.15, age=0.99),
    _proto("ocean",   1,
           temperature=0.30, pressure=0.72, gravity=0.65, solidity=0.02,
           humidity=0.99, toxicity=0.02, windspeed=0.10, visibility=0.45,
           luminosity=0.22, radiation=0.02, magnetism=0.05, volatility=0.15,
           flora=0.25, fauna=0.92, decay=0.10, age=0.72),
    _proto("desert",  1,
           temperature=0.99, pressure=0.52, gravity=0.92, solidity=0.55,
           humidity=0.00, toxicity=0.02, windspeed=0.30, visibility=0.99,
           luminosity=0.99, radiation=0.42, magnetism=0.08, volatility=0.10,
           flora=0.00, fauna=0.02, decay=0.02, age=0.82),
    _proto("forest",  1,
           temperature=0.55, pressure=0.62, gravity=0.88, solidity=0.65,
           humidity=0.75, toxicity=0.02, windspeed=0.05, visibility=0.50,
           luminosity=0.45, radiation=0.02, magnetism=0.02, volatility=0.05,
           flora=0.99, fauna=0.70, decay=0.12, age=0.55),
    _proto("tundra",  1,
           temperature=0.00, pressure=0.52, gravity=0.92, solidity=0.78,
           humidity=0.18, toxicity=0.00, windspeed=0.58, visibility=0.75,
           luminosity=0.60, radiation=0.02, magnetism=0.05, volatility=0.05,
           flora=0.00, fauna=0.02, decay=0.00, age=0.92),
    _proto("swamp",   1,
           temperature=0.62, pressure=0.62, gravity=0.82, solidity=0.35,
           humidity=0.99, toxicity=0.55, windspeed=0.00, visibility=0.08,
           luminosity=0.05, radiation=0.05, magnetism=0.02, volatility=0.05,
           flora=0.99, fauna=0.62, decay=0.99, age=0.75),
    _proto("peak",    1,
           temperature=0.00, pressure=0.05, gravity=0.65, solidity=0.82,
           humidity=0.08, toxicity=0.00, windspeed=0.82, visibility=0.92,
           luminosity=0.88, radiation=0.05, magnetism=0.02, volatility=0.22,
           flora=0.00, fauna=0.02, decay=0.00, age=0.90),
    _proto("shore",   1,
           temperature=0.52, pressure=0.55, gravity=0.82, solidity=0.48,
           humidity=0.68, toxicity=0.02, windspeed=0.42, visibility=0.88,
           luminosity=0.80, radiation=0.02, magnetism=0.02, volatility=0.25,
           flora=0.22, fauna=0.45, decay=0.05, age=0.38),
    _proto("sky",     1,
           temperature=0.42, pressure=0.02, gravity=0.02, solidity=0.00,
           humidity=0.02, toxicity=0.00, windspeed=0.95, visibility=0.99,
           luminosity=0.98, radiation=0.08, magnetism=0.00, volatility=0.88,
           flora=0.00, fauna=0.05, decay=0.00, age=0.00),
    # Gen 2
    _proto("volcano",    2, temperature=0.95, pressure=0.90, gravity=0.90, solidity=0.80,
           humidity=0.40, toxicity=0.50, windspeed=0.30, visibility=0.30,
           luminosity=0.55, radiation=0.30, volatility=0.80,
           flora=0.02, fauna=0.05, decay=0.20, age=0.70),
    _proto("abyss",      2, temperature=0.10, pressure=1.00, gravity=0.80, solidity=0.15,
           humidity=1.00, toxicity=0.30, windspeed=0.05, visibility=0.00,
           luminosity=0.00, volatility=0.10, flora=0.10, fauna=0.15, decay=0.40, age=0.95),
    _proto("glacier",    2, temperature=0.05, pressure=0.70, gravity=0.90, solidity=0.85,
           humidity=0.50, windspeed=0.30, visibility=0.75,
           luminosity=0.65, volatility=0.05, flora=0.05, fauna=0.08, age=0.90),
    _proto("badlands",   2, temperature=0.70, pressure=0.60, gravity=0.85, solidity=0.65,
           humidity=0.10, toxicity=0.40, windspeed=0.30, visibility=0.75,
           luminosity=0.75, radiation=0.40, volatility=0.50,
           flora=0.05, fauna=0.10, decay=0.50, age=0.85),
    _proto("tempest",    2, temperature=0.35, pressure=0.95, gravity=0.55, solidity=0.05,
           humidity=0.85, windspeed=1.00, visibility=0.10,
           luminosity=0.20, radiation=0.15, volatility=0.98, flora=0.00, fauna=0.05),
    _proto("jungle",     2, temperature=0.80, pressure=0.60, gravity=0.85, solidity=0.55,
           humidity=0.95, toxicity=0.15, windspeed=0.05, visibility=0.30,
           luminosity=0.35, volatility=0.20, flora=0.95, fauna=0.80, decay=0.40, age=0.50),
    _proto("permafrost", 2, temperature=0.02, pressure=0.80, gravity=0.90, solidity=0.90,
           humidity=0.40, windspeed=0.15, visibility=0.55,
           luminosity=0.50, volatility=0.05, flora=0.02, fauna=0.05, age=0.99),
    _proto("biolume",    2, temperature=0.20, pressure=0.95, gravity=0.70, solidity=0.15,
           humidity=1.00, windspeed=0.02, visibility=0.30, luminosity=0.35, volatility=0.15,
           flora=0.50, fauna=0.70, decay=0.30, age=0.80, arcane=0.20, resonance=0.25),
    _proto("ashfield",   2, temperature=0.75, pressure=0.70, gravity=0.85, solidity=0.50,
           humidity=0.15, toxicity=0.60, windspeed=0.40, visibility=0.10,
           luminosity=0.15, radiation=0.35, volatility=0.50,
           flora=0.00, fauna=0.05, decay=0.60, age=0.80),
    _proto("maelstrom",  2, temperature=0.35, pressure=0.90, gravity=0.65, solidity=0.10,
           humidity=0.95, windspeed=0.90, visibility=0.10,
           luminosity=0.15, volatility=0.95, flora=0.00, fauna=0.10, age=0.30),
    # Gen 3
    _proto("underworld",    3, temperature=0.80, pressure=0.90, gravity=0.95, solidity=0.70,
           humidity=0.50, toxicity=0.35, windspeed=0.05, visibility=0.02,
           luminosity=0.02, radiation=0.20, volatility=0.40,
           flora=0.10, fauna=0.25, decay=0.65, age=0.99,
           arcane=0.55, resonance=0.45, corruption=0.80),
    _proto("sky_citadel",   3, temperature=0.35, pressure=0.08, gravity=0.12, solidity=0.50,
           humidity=0.25, windspeed=0.50, visibility=0.95, luminosity=0.95, volatility=0.28,
           flora=0.20, fauna=0.22, age=0.85, arcane=0.55, resonance=0.50, sanctity=0.80),
    _proto("fae_realm",     3, temperature=0.50, pressure=0.42, gravity=0.48, solidity=0.28,
           humidity=0.68, windspeed=0.22, visibility=0.72, luminosity=0.68, volatility=0.42,
           flora=0.99, fauna=0.65, decay=0.02, age=0.92,
           arcane=0.88, resonance=0.75, sanctity=0.50, corruption=0.00),
    _proto("sea_of_souls",  3, temperature=0.20, pressure=0.48, gravity=0.38, solidity=0.02,
           humidity=0.85, windspeed=0.15, visibility=0.05, luminosity=0.05, volatility=0.55,
           flora=0.02, fauna=0.15, decay=0.55, age=0.99,
           arcane=0.88, resonance=0.55, corruption=0.65, sanctity=0.00),
    _proto("titan_forge",   3, temperature=0.95, pressure=0.85, gravity=0.90, solidity=0.80,
           humidity=0.30, toxicity=0.40, windspeed=0.20, visibility=0.25,
           luminosity=0.60, radiation=0.35, volatility=0.75,
           flora=0.00, fauna=0.05, age=0.90, arcane=0.45, resonance=0.40),
    _proto("sunken_kingdom",3, temperature=0.22, pressure=0.92, gravity=0.75, solidity=0.62,
           humidity=0.99, windspeed=0.00, visibility=0.12, luminosity=0.12, magnetism=0.30,
           volatility=0.18, flora=0.28, fauna=0.38, decay=0.72, age=0.99,
           arcane=0.60, resonance=0.40, corruption=0.55),
    _proto("frost_citadel", 3, temperature=0.00, pressure=0.50, gravity=0.82, solidity=0.92,
           humidity=0.32, windspeed=0.22, visibility=0.88, luminosity=0.78, volatility=0.05,
           flora=0.02, fauna=0.08, age=0.99, arcane=0.55, resonance=0.48, sanctity=0.72),
    _proto("storm_throne",  3, temperature=0.38, pressure=0.72, gravity=0.52, solidity=0.32,
           humidity=0.78, windspeed=0.92, visibility=0.32, luminosity=0.42,
           radiation=0.22, magnetism=0.55, volatility=0.98,
           flora=0.05, fauna=0.08, age=0.82,
           arcane=0.55, resonance=0.62, sanctity=0.50),
    _proto("verdant_ruin",  3, temperature=0.62, pressure=0.62, gravity=0.88, solidity=0.68,
           humidity=0.82, windspeed=0.08, visibility=0.38, luminosity=0.38, volatility=0.22,
           flora=0.99, fauna=0.55, decay=0.72, age=0.99,
           arcane=0.50, resonance=0.35, sanctity=0.05, corruption=0.30),
    _proto("echo_deep",     3, temperature=0.18, pressure=0.88, gravity=0.90, solidity=0.90,
           humidity=0.48, windspeed=0.00, visibility=0.00, luminosity=0.00, magnetism=0.88,
           volatility=0.48, flora=0.02, fauna=0.12, decay=0.38, age=0.99,
           arcane=0.72, resonance=0.99, corruption=0.25),
    # Gen 4
    _proto("black_hole",     4, temperature=0.00, pressure=1.00, gravity=1.00, solidity=1.00,
           humidity=0.00, windspeed=0.00, visibility=0.00, luminosity=0.00,
           radiation=1.00, magnetism=1.00, volatility=0.90, decay=0.90, age=0.99,
           arcane=0.80, resonance=0.90, corruption=0.70),
    _proto("sun",            4, temperature=1.00, pressure=0.30, gravity=0.50, solidity=0.10,
           humidity=0.00, toxicity=0.70, windspeed=0.50, visibility=1.00,
           luminosity=1.00, radiation=1.00, magnetism=0.60, volatility=0.80,
           arcane=0.40, resonance=0.50),
    _proto("nebula",         4, temperature=0.50, pressure=0.05, gravity=0.02, solidity=0.02,
           humidity=0.10, windspeed=0.50, visibility=0.85,
           luminosity=0.90, radiation=0.60, magnetism=0.40, volatility=0.70,
           arcane=0.65, resonance=0.50),
    _proto("moon",           4, temperature=0.15, pressure=0.00, gravity=0.18, solidity=0.92,
           humidity=0.00, windspeed=0.00, visibility=0.82,
           luminosity=0.52, radiation=0.28, volatility=0.00,
           flora=0.00, fauna=0.00, decay=0.00, age=0.99,
           arcane=0.20, resonance=0.15),
    _proto("void",           4, temperature=0.00, pressure=0.00, gravity=0.00, solidity=0.00,
           humidity=0.00, windspeed=0.00, visibility=0.00, luminosity=0.00,
           radiation=0.00, magnetism=0.00, volatility=0.00,
           flora=0.00, fauna=0.00, decay=0.00, age=0.00,
           arcane=0.60, resonance=0.00, corruption=0.50, sanctity=0.00),
    _proto("pulsar",         4, temperature=0.82, pressure=0.52, gravity=0.72, solidity=0.28,
           humidity=0.00, windspeed=0.62, visibility=0.58,
           luminosity=0.82, radiation=0.99, magnetism=0.99, volatility=0.88,
           arcane=0.52, resonance=0.78),
    _proto("asteroid_field", 4, temperature=0.08, pressure=0.00, gravity=0.12, solidity=0.72,
           humidity=0.00, windspeed=0.22, visibility=0.72,
           luminosity=0.48, radiation=0.22, magnetism=0.08, volatility=0.42,
           flora=0.00, fauna=0.00, decay=0.00, age=0.92,
           arcane=0.10, resonance=0.05),
    _proto("star_cluster",   4, temperature=0.72, pressure=0.08, gravity=0.18, solidity=0.04,
           humidity=0.04, windspeed=0.42, visibility=0.99,
           luminosity=0.99, radiation=0.82, magnetism=0.52, volatility=0.68,
           arcane=0.58, resonance=0.62),
    _proto("wormhole",       4, temperature=0.50, pressure=0.50, gravity=0.50, solidity=0.08,
           humidity=0.18, windspeed=0.72, visibility=0.38,
           luminosity=0.52, radiation=0.52, magnetism=0.62, volatility=0.99,
           arcane=0.92, resonance=0.72, corruption=0.28),
    _proto("dark_matter",    4, temperature=0.00, pressure=0.08, gravity=0.38, solidity=0.00,
           humidity=0.00, windspeed=0.00, visibility=0.00, luminosity=0.00,
           radiation=0.08, magnetism=0.52, volatility=0.18,
           flora=0.00, fauna=0.00, decay=0.00, age=0.00,
           arcane=0.85, resonance=0.42, corruption=0.18),
    # Gen 5
    _proto("heaven",      5, temperature=0.60, pressure=0.20, gravity=0.08, solidity=0.05,
           humidity=0.38, windspeed=0.18, visibility=0.99, luminosity=0.99, volatility=0.02,
           flora=0.55, fauna=0.42, decay=0.00, age=0.50,
           arcane=0.99, resonance=0.82, sanctity=0.99, corruption=0.00),
    _proto("hell",        5, temperature=0.99, pressure=0.88, gravity=0.82, solidity=0.62,
           humidity=0.28, toxicity=0.92, windspeed=0.42, visibility=0.08,
           luminosity=0.25, radiation=0.55, volatility=0.92,
           flora=0.02, fauna=0.28, decay=0.92, age=0.99,
           arcane=0.96, resonance=0.58, corruption=0.99, sanctity=0.00),
    _proto("olympus",     5, temperature=0.58, pressure=0.22, gravity=0.22, solidity=0.42,
           humidity=0.42, windspeed=0.62, visibility=0.98, luminosity=0.98, magnetism=0.42,
           volatility=0.65, flora=0.42, fauna=0.38, decay=0.00, age=0.92,
           arcane=0.92, resonance=0.85, sanctity=0.88, corruption=0.00),
    _proto("the_between", 5, temperature=0.25, pressure=0.08, gravity=0.04, solidity=0.01,
           humidity=0.28, windspeed=0.48, visibility=0.18, luminosity=0.15, volatility=0.88,
           flora=0.00, fauna=0.00, decay=0.45, age=0.99,
           arcane=0.99, resonance=0.38, corruption=0.45, sanctity=0.35),
    _proto("astral_sea",  5, temperature=0.42, pressure=0.08, gravity=0.04, solidity=0.01,
           humidity=0.32, windspeed=0.28, visibility=0.78, luminosity=0.78, magnetism=0.32,
           volatility=0.58, flora=0.00, fauna=0.00, decay=0.00, age=0.50,
           arcane=0.99, resonance=0.95, sanctity=0.65, corruption=0.00),
    _proto("chaos_realm", 5, temperature=0.50, pressure=0.50, gravity=0.50, solidity=0.50,
           humidity=0.50, toxicity=0.50, windspeed=0.50, visibility=0.50,
           luminosity=0.50, radiation=0.50, magnetism=0.50, volatility=0.99,
           flora=0.50, fauna=0.50, decay=0.50, age=0.50,
           arcane=0.88, resonance=0.50, corruption=0.55, sanctity=0.45),
    _proto("creation",    5, temperature=0.99, pressure=0.99, gravity=0.99, solidity=0.99,
           humidity=0.99, toxicity=0.99, windspeed=0.99, visibility=0.99,
           luminosity=0.99, radiation=0.99, magnetism=0.99, volatility=0.99,
           flora=0.99, fauna=0.99, decay=0.00, age=0.00,
           arcane=0.99, resonance=0.99, corruption=0.50, sanctity=0.50),
    _proto("purgatory",   5, temperature=0.50, pressure=0.50, gravity=0.50, solidity=0.50,
           humidity=0.50, toxicity=0.18, windspeed=0.18, visibility=0.50,
           luminosity=0.50, volatility=0.28, flora=0.18, fauna=0.18, decay=0.50, age=0.85,
           arcane=0.65, resonance=0.55, corruption=0.50, sanctity=0.50),
    _proto("elysium",     5, temperature=0.62, pressure=0.42, gravity=0.42, solidity=0.32,
           humidity=0.68, windspeed=0.18, visibility=0.88, luminosity=0.88, volatility=0.08,
           flora=0.99, fauna=0.72, decay=0.00, age=0.62,
           arcane=0.96, resonance=0.88, sanctity=0.96, corruption=0.00),
    _proto("nirvana",     5, temperature=0.50, pressure=0.28, gravity=0.08, solidity=0.00,
           humidity=0.28, windspeed=0.00, visibility=0.82, luminosity=0.72, volatility=0.00,
           flora=0.00, fauna=0.00, decay=0.00, age=0.50,
           arcane=0.92, resonance=0.99, sanctity=0.92, corruption=0.00),
]

PROTO_NAMES = [p["name"] for p in PROTOTYPE_LIBRARY]
PROTO_VECS  = [[p["traits"].get(t, 0.0) for t in ALL_TRAITS] for p in PROTOTYPE_LIBRARY]
PROTO_GENS  = [p["gen_affinity"] for p in PROTOTYPE_LIBRARY]


# ---------------------------------------------------------------------------
# ML recipes
# ---------------------------------------------------------------------------

def _load_recipes(path: str = "recipes.json") -> dict:
    for candidate in [path, str(Path(__file__).parent / "recipes.json")]:
        p = Path(candidate)
        if p.exists():
            with open(p) as f:
                return json.load(f)
    return {}


RECIPES: dict[str, dict] = _load_recipes()


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x * x for x in a))
    mb  = math.sqrt(sum(x * x for x in b))
    if ma == 0 or mb == 0:
        return 0.0
    return dot / (ma * mb)


def _euclidean_dist(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _softmax(scores: list[float], temperature: float = SOFTMAX_TEMPERATURE) -> list[float]:
    scaled = [s / max(temperature, 1e-9) for s in scores]
    max_s  = max(scaled)
    exps   = [math.exp(s - max_s) for s in scaled]
    total  = sum(exps)
    return [e / total for e in exps]


def _normalize(d: dict[str, float]) -> dict[str, float]:
    total = sum(d.values())
    if total == 0:
        return {k: 1.0 / len(d) for k in d}
    return {k: v / total for k, v in d.items()}


def _clamp01(d: dict[str, float]) -> dict[str, float]:
    return {k: max(0.0, min(1.0, v)) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Generation math
# ---------------------------------------------------------------------------

def _compute_child_gen(parent_gens: list[int], ratios: list[float]) -> int:
    max_gen   = max(parent_gens)
    dom_idx   = max(range(3), key=lambda i: ratios[i])
    dom_gen   = parent_gens[dom_idx]
    dom_ratio = ratios[dom_idx]
    if dom_ratio > 0.66 and dom_gen < max_gen:
        return dom_gen + 1
    return max_gen + 1


# ---------------------------------------------------------------------------
# Trait blending
# ---------------------------------------------------------------------------

def _blend_traits(
    parent_traits: list[dict[str, float]],
    ratios: list[float],
    child_gen: int,
) -> dict[str, float]:
    means = {t: sum(pt.get(t, 0.0) * r for pt, r in zip(parent_traits, ratios))
             for t in ALL_TRAITS}

    dominance     = max(ratios)
    sigma_scale   = max(0.0, min(1.0, 1.0 - ((dominance - 1/3) / (2/3))))
    effective_sig = BASE_TRAIT_SIGMA * sigma_scale

    variances = {
        t: sum(r * (pt.get(t, 0.0) - means[t]) ** 2
               for pt, r in zip(parent_traits, ratios))
        for t in ALL_TRAITS
    }

    blended: dict[str, float] = {}
    for t in ALL_TRAITS:
        mean      = means[t]
        agreement = 1.0 - min(variances[t] / 0.25, 1.0)
        extreme   = 1.0 if mean >= 0.5 else 0.0
        amplified = mean + agreement * (extreme - mean) * AMPLIFICATION_FACTOR
        noisy     = amplified + random.gauss(0, effective_sig)
        if t in EMERGENT and child_gen > 0:
            noisy += abs(random.gauss(0, EMERGENT_DRIFT_SIGMA * child_gen))
        blended[t] = noisy

    return _clamp01(blended)


def _blend_weights(
    parent_weights: list[dict[str, float]],
    ratios: list[float],
    dominance: float,
) -> dict[str, float]:
    merged: dict[str, float] = {}
    for pw, r in zip(parent_weights, ratios):
        for k, v in pw.items():
            merged[k] = merged.get(k, 0.0) + v * r

    w_sigma = max(0.0, 0.04 * (1.0 - ((dominance - 1/3) / (2/3))))
    noisy   = {k: max(0.0, v + random.gauss(0, w_sigma)) for k, v in merged.items()}
    noisy   = {k: v for k, v in noisy.items() if v > 1e-4}
    return _normalize(noisy)


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------

def _name_from_library(trait_vec: list[float], child_gen: int) -> str:
    # Hard gate: only consider prototypes within 1 generation of child_gen.
    # This prevents gen-1 blends from ever naming as black_hole, void, etc.
    scores = []
    for pvec, pg in zip(PROTO_VECS, PROTO_GENS):
        if abs(child_gen - pg) > 1:
            scores.append(-999.0)
            continue
        sim     = _cosine_sim(trait_vec, pvec)
        dist    = _euclidean_dist(trait_vec, pvec)
        euc_pen = dist / 4.47
        score   = (0.7 * sim - 0.3 * euc_pen) - GEN_BIAS_STRENGTH * abs(child_gen - pg)
        scores.append(score)
    probs  = _softmax(scores)
    chosen = random.choices(PROTOTYPE_LIBRARY, weights=probs, k=1)[0]
    return chosen["name"]


def _name_from_api(trait_vec: list[float], child_gen: int) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _name_from_library(trait_vec, child_gen)

    notable = sorted(
        [(ALL_TRAITS[i], round(v, 2)) for i, v in enumerate(trait_vec) if v > 0.10],
        key=lambda x: -x[1],
    )[:12]
    trait_desc = ", ".join(f"{t}={v}" for t, v in notable)

    prompt = (
        f"You are naming environments in a creature evolution game. "
        f"Generation 0 = mundane earthly, generation 15 = transcendent/cosmic. "
        f"This is generation {child_gen}. Traits: {trait_desc}. "
        f"Reply with ONLY a single lowercase word or snake_case phrase "
        f"(no spaces, max 2 words joined by underscore). "
        f"Evocative, logical, appropriate for the generation. No explanation."
    )

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 20,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                word = content[0]["text"].strip().lower()
                word = "".join(c for c in word if c.isalpha() or c == "_")
                if word:
                    return word
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass

    return _name_from_library(trait_vec, child_gen)


def _select_name(trait_vec: list[float], child_gen: int) -> str:
    if child_gen <= API_GEN_THRESHOLD:
        return _name_from_library(trait_vec, child_gen)
    return _name_from_api(trait_vec, child_gen)


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

def generate_next_environment(
    parents:     list[Environment],
    time_ratios: Optional[list[float]] = None,
) -> Environment:
    """
    Blend three parent environments into a new child.

    Parameters
    ----------
    parents     : exactly 3 Environment objects (repeats allowed)
    time_ratios : time spent in each parent, auto-normalised.
                  Defaults to equal thirds.

    Returns
    -------
    New Environment — stochastic but biased toward logically close outputs.
    Same inputs will not always produce the same name, but will always
    produce similar trait profiles.
    """
    if len(parents) != 3:
        raise ValueError("Exactly 3 parents required.")
    if time_ratios is None:
        time_ratios = [1/3, 1/3, 1/3]
    if len(time_ratios) != 3:
        raise ValueError("time_ratios must have 3 values.")
    if any(r < 0 for r in time_ratios):
        raise ValueError("time_ratios must be non-negative.")
    total = sum(time_ratios)
    if total == 0:
        raise ValueError("At least one ratio must be > 0.")

    ratios    = [r / total for r in time_ratios]
    dominance = max(ratios)
    child_gen = _compute_child_gen([p.generation for p in parents], ratios)

    final_weights = _blend_weights([p.weights for p in parents], ratios, dominance)
    final_traits  = _blend_traits([p.traits  for p in parents], ratios, child_gen)
    trait_vec     = [final_traits.get(t, 0.0) for t in ALL_TRAITS]
    chosen_name   = _select_name(trait_vec, child_gen)

    return Environment(
        name=chosen_name,
        weights=final_weights,
        traits=final_traits,
        generation=child_gen,
        parents=[p.name for p in parents],
    )


# ---------------------------------------------------------------------------
# Recipe API
# ---------------------------------------------------------------------------

def get_recipe(target_name: str) -> Optional[dict]:
    """Return the ML-fitted recipe for a target, or None if not found."""
    return RECIPES.get(target_name)


def recipe_summary(target_name: str) -> str:
    """Human-readable description of how to reach a target environment."""
    r = get_recipe(target_name)
    if r is None:
        if target_name in BASE_ENVIRONMENTS:
            return f"'{target_name}' is a base environment (generation 0)."
        return f"No recipe found for '{target_name}'."

    # Merge duplicate parents — air(26%) + air(26%) + earth(47%) → air(52%) + earth(47%)
    merged: dict[str, float] = {}
    for p, rv in zip(r["parents"], r["ratios"]):
        merged[p] = merged.get(p, 0.0) + rv
    parents_str = " + ".join(
        f"{p} ({rv:.0%})" for p, rv in sorted(merged.items(), key=lambda x: -x[1])
    )

    quality = "exact hit" if r.get("exact_hit") else f"near (names as '{r['names_as']}')"
    return (
        f"'{target_name}' — gen {r['generation']}, {quality}, "
        f"cos={r['cosine_sim']:.3f}\n"
        f"  Recipe: {parents_str}"
    )


# ---------------------------------------------------------------------------
# World registry
# ---------------------------------------------------------------------------

class World:
    """
    Tracks every environment ever generated, seeded with the base envs.
    Provides free generation, recipe-guided targeting, and chain resolution.
    """

    def __init__(self):
        self.environments: dict[str, Environment] = dict(BASE_ENVIRONMENTS)

    def get(self, name: str) -> Environment:
        if name not in self.environments:
            raise KeyError(f"Environment '{name}' not found in world.")
        return self.environments[name]

    def _add_free(self, env: Environment) -> Environment:
        """Add a freely-generated environment with collision suffixes."""
        key = env.name
        if key in self.environments:
            i = 2
            while f"{key}_{i}" in self.environments:
                i += 1
            key = f"{key}_{i}"
        env = Environment(key, env.weights, env.traits, env.generation, env.parents)
        self.environments[key] = env
        return env

    def _add_canonical(self, name: str, env: Environment) -> Environment:
        """Store under exact canonical name, overwriting previous entry."""
        stored = Environment(name, env.weights, env.traits, env.generation, env.parents)
        self.environments[name] = stored
        return stored

    def generate(
        self,
        parent_names: list[str],
        time_ratios:  Optional[list[float]] = None,
    ) -> Environment:
        """Generate freely from named parents. Collision names get _2, _3 suffix."""
        parents = [self.get(n) for n in parent_names]
        return self._add_free(generate_next_environment(parents, time_ratios))

    def generate_toward(self, target_name: str) -> Optional[Environment]:
        """
        Use the ML-fitted recipe to aim at a specific target.
        The result is always stored under the canonical target_name so that
        recipe chains can find it. Overwrites any previous canonical entry.
        Still stochastic in traits and possibly in the chosen name label,
        but the trait profile is as close as the recipe allows.
        Returns None if no recipe exists.
        """
        recipe = get_recipe(target_name)
        if recipe is None:
            return None
        missing = [p for p in recipe["parents"] if p not in self.environments]
        if missing:
            raise KeyError(
                f"Recipe for '{target_name}' needs parents not in world: {missing}. "
                f"Call ensure_recipe_chain('{target_name}') first."
            )
        parents = [self.get(p) for p in recipe["parents"]]
        child   = generate_next_environment(parents, recipe["ratios"])
        return self._add_canonical(target_name, child)

    def ensure_recipe_chain(self, target_name: str) -> list[str]:
        """
        Recursively ensure all ancestors of target_name exist under their
        canonical names, then generate the target itself.
        Skips anything already present. Returns list of names added.
        """
        if target_name in self.environments or target_name in BASE_ENVIRONMENTS:
            return []

        recipe = get_recipe(target_name)
        if recipe is None:
            raise ValueError(f"No recipe for '{target_name}' and not in world.")

        added = []
        for parent_name in recipe["parents"]:
            if parent_name not in self.environments:
                added.extend(self.ensure_recipe_chain(parent_name))

        env = self.generate_toward(target_name)
        if env is not None:
            added.append(env.name)
        return added

    def list_by_generation(self) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for name, env in self.environments.items():
            out.setdefault(env.generation, []).append(name)
        return {g: sorted(names) for g, names in sorted(out.items())}

    def recipe_book(self) -> str:
        lines = ["RECIPE BOOK", "=" * 60]
        for gen in range(1, 6):
            gen_recipes = [(n, r) for n, r in RECIPES.items()
                           if r.get("generation") == gen]
            if not gen_recipes:
                continue
            lines.append(f"\nGen {gen}:")
            for name, _ in sorted(gen_recipes):
                lines.append(f"  {recipe_summary(name)}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    random.seed(42)

    # Build a world with all recipe environments available as parents
    world = World()
    for _target in list(RECIPES.keys()):
        try:
            world.ensure_recipe_chain(_target)
        except Exception:
            pass

    def show(label, parents, ratios, runs=5):
        """Generate `runs` times and print results cleanly."""
        p1, p2, p3 = parents
        g1 = world.get(p1).generation
        g2 = world.get(p2).generation
        g3 = world.get(p3).generation
        r  = [rv / sum(ratios) for rv in ratios]
        results = [world.generate(parents, ratios).name for _ in range(runs)]
        print(f"  {label}")
        print(f"    {p1}(gen{g1}) {r[0]:.0%}  +  {p2}(gen{g2}) {r[1]:.0%}  +  {p3}(gen{g3}) {r[2]:.0%}")
        print(f"    → {results}")
        print()

    # ── Gen 0 + 0 + 0 → always gen 1 ────────────────────────────────────────
    print("=" * 60)
    print("GEN 0 + 0 + 0  →  gen 1")
    print("=" * 60)
    show("air-heavy",   ["air", "water", "earth"], [0.70, 0.20, 0.10])
    show("water-heavy", ["water", "earth", "air"], [0.70, 0.20, 0.10])
    show("earth-heavy", ["earth", "air",  "water"],[0.70, 0.15, 0.15])
    show("balanced",    ["air", "water", "earth"], [0.34, 0.33, 0.33])

    # ── Gen 1 + 1 + 1 → gen 2 ────────────────────────────────────────────────
    print("=" * 60)
    print("GEN 1 + 1 + 1  →  gen 2")
    print("=" * 60)
    show("storm + cave + ocean",    ["storm", "cave",   "ocean"],  [0.50, 0.30, 0.20])
    show("desert + forest + tundra",["desert","forest", "tundra"], [0.50, 0.30, 0.20])
    show("swamp + peak + shore",    ["swamp", "peak",   "shore"],  [0.50, 0.30, 0.20])
    show("sky + ocean + cave",      ["sky",   "ocean",  "cave"],   [0.34, 0.33, 0.33])

    # ── Gen 0 + 1 + 1 → gen 1 if gen-0 dominates, else gen 2 ─────────────────
    print("=" * 60)
    print("GEN 0 + 1 + 1  →  gen 1 (if gen-0 > 66%) or gen 2")
    print("=" * 60)
    show("air 80% dominant → gen 1",  ["air",   "storm", "cave"],  [0.80, 0.10, 0.10])
    show("air 50% majority → gen 2",  ["air",   "storm", "cave"],  [0.50, 0.25, 0.25])
    show("earth 80% dominant → gen 1",["earth", "forest","swamp"], [0.80, 0.10, 0.10])
    show("earth 50% majority → gen 2",["earth", "forest","swamp"], [0.50, 0.25, 0.25])

    # ── Gen 2 + 2 + 2 → gen 3 ────────────────────────────────────────────────
    print("=" * 60)
    print("GEN 2 + 2 + 2  →  gen 3")
    print("=" * 60)
    show("volcano + glacier + abyss",    ["volcano","glacier","abyss"],    [0.50, 0.30, 0.20])
    show("jungle + permafrost + badlands",["jungle","permafrost","badlands"],[0.50, 0.30, 0.20])
    show("tempest + ashfield + maelstrom",["tempest","ashfield","maelstrom"],[0.34,0.33,0.33])

    # ── Gen 1 + 2 + 2 → gen 2 or 3 ───────────────────────────────────────────
    print("=" * 60)
    print("GEN 1 + 2 + 2  →  gen 2 (if gen-1 > 66%) or gen 3")
    print("=" * 60)
    show("storm 80% → gen 2",   ["storm","volcano","glacier"], [0.80, 0.10, 0.10])
    show("storm 50% → gen 3",   ["storm","volcano","glacier"], [0.50, 0.25, 0.25])
    show("forest 80% → gen 2",  ["forest","jungle","biolume"], [0.80, 0.10, 0.10])
    show("forest 50% → gen 3",  ["forest","jungle","biolume"], [0.50, 0.25, 0.25])

    # ── Gen 3 + 3 + 3 → gen 4 ────────────────────────────────────────────────
    print("=" * 60)
    print("GEN 3 + 3 + 3  →  gen 4")
    print("=" * 60)
    show("underworld + sky_citadel + titan_forge",
         ["underworld","sky_citadel","titan_forge"], [0.50, 0.30, 0.20])
    show("fae_realm + verdant_ruin + echo_deep",
         ["fae_realm","verdant_ruin","echo_deep"],   [0.50, 0.30, 0.20])
    show("frost_citadel + storm_throne + sunken_kingdom",
         ["frost_citadel","storm_throne","sunken_kingdom"], [0.34,0.33,0.33])

    # ── Gen 2 + 3 + 3 → gen 3 or 4 ───────────────────────────────────────────
    print("=" * 60)
    print("GEN 2 + 3 + 3  →  gen 3 (if gen-2 > 66%) or gen 4")
    print("=" * 60)
    show("volcano 80% → gen 3",  ["volcano","underworld","titan_forge"],[0.80,0.10,0.10])
    show("volcano 50% → gen 4",  ["volcano","underworld","titan_forge"],[0.50,0.25,0.25])

    # ── Gen 4 + 4 + 4 → gen 5 ────────────────────────────────────────────────
    print("=" * 60)
    print("GEN 4 + 4 + 4  →  gen 5")
    print("=" * 60)
    show("black_hole + nebula + wormhole",
         ["black_hole","nebula","wormhole"], [0.50, 0.30, 0.20])
    show("sun + moon + pulsar",
         ["sun","moon","pulsar"], [0.50, 0.30, 0.20])
    show("void + dark_matter + asteroid_field",
         ["void","dark_matter","asteroid_field"], [0.34,0.33,0.33])

"""Trait vocabulary shared by the environment generator and naming module.

The hand-curated prototype library that used to live here was removed in
favor of fully algorithmic naming (see
docs/design/procedural-environment-generation.md) — only the trait key list
survives, since every Environment's `traits` dict is keyed by it.
"""

ALL_TRAITS = [
    "temperature",
    "pressure",
    "gravity",
    "solidity",
    "humidity",
    "toxicity",
    "windspeed",
    "visibility",
    "luminosity",
    "radiation",
    "magnetism",
    "volatility",
    "flora",
    "fauna",
    "decay",
    "age",
    "arcane",
    "resonance",
    "corruption",
    "sanctity",
]

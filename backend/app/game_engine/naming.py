"""Procedural naming: word banks + tier ladder + emergent qualifiers.

Pure vocabulary data + composition logic, kept separate from
environment_generator.py's blending/tier math the same way prototypes.py
used to hold gen-1 data before naming became fully algorithmic. See
docs/design/procedural-environment-generation.md for the design this
implements.
"""

import math
import random

HYBRID_THRESHOLD = 0.2

ELEMENT_WORDS = {
    "fire": ["Ember", "Cinder", "Blaze", "Flame", "Scorch", "Magma", "Pyre"],
    "water": ["Tide", "Current", "Depths", "Mist", "Brine", "Torrent", "Abyss"],
    "earth": ["Stone", "Crag", "Bedrock", "Root", "Vein", "Ridge", "Loam"],
    "air": ["Gale", "Zephyr", "Squall", "Cloud", "Vortex", "Draft", "Sky"],
}

HYBRID_PATTERNS = [
    "{secondary} {dominant}",
    "{dominant} of {secondary}",
]

TIER_EPITHETS = [
    "",
    "Greater ",
    "Grand ",
    "Ascendant ",
    "Primordial ",
    "Celestial ",
    "Transcendent ",
]

EMERGENT_THRESHOLD = 0.6
EMERGENT_QUALIFIERS = {
    "corruption": "Corrupted",
    "sanctity": "Sanctified",
    "arcane": "Arcane",
    "resonance": "Resonant",
}

_ROMAN_VALUES = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]  # fmt: skip


def _to_roman(n: int) -> str:
    if n > 3999:
        return str(n)
    parts = []
    remaining = n
    for value, symbol in _ROMAN_VALUES:
        count, remaining = divmod(remaining, value)
        parts.append(symbol * count)
    return "".join(parts)


def _tier_epithet(tier: float) -> tuple[str, str]:
    """Returns (epithet_prefix, numeral_suffix)."""
    index = max(0, math.floor(tier) - 1)
    if index < len(TIER_EPITHETS):
        return TIER_EPITHETS[index], ""
    overflow = index - len(TIER_EPITHETS) + 2
    return TIER_EPITHETS[-1], f" {_to_roman(overflow)}"


def compose_name(weights: dict[str, float], traits: dict[str, float], tier: float) -> str:
    full_weights = {el: weights.get(el, 0.0) for el in ELEMENT_WORDS}
    ordered = sorted(full_weights.items(), key=lambda kv: kv[1], reverse=True)
    dominant, dominant_share = ordered[0]
    second, second_share = ordered[1]

    if dominant_share - second_share >= HYBRID_THRESHOLD:
        base_word = random.choice(ELEMENT_WORDS[dominant])
    else:
        pattern = random.choice(HYBRID_PATTERNS)
        base_word = pattern.format(
            dominant=random.choice(ELEMENT_WORDS[dominant]),
            secondary=random.choice(ELEMENT_WORDS[second]),
        )

    epithet, numeral_suffix = _tier_epithet(tier)

    emergent_suffix = ""
    top_trait, top_score = max(
        ((t, traits.get(t, 0.0)) for t in EMERGENT_QUALIFIERS), key=lambda kv: kv[1]
    )
    if top_score >= EMERGENT_THRESHOLD:
        emergent_suffix = f" {EMERGENT_QUALIFIERS[top_trait]}"

    return f"{epithet}{base_word}{numeral_suffix}{emergent_suffix}"

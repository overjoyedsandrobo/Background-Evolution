"""Procedural naming: tier-banded vocabulary + composition logic.

Pure vocabulary data + composition logic, kept separate from
environment_generator.py's blending/tier math the same way prototypes.py
used to hold gen-1 data before naming became fully algorithmic. See
docs/design/procedural-environment-generation.md for the design this
implements.

Naming escalates through 6 tier bands instead of stapling an intensifier
onto one flat vocabulary: early tiers read as real, recognizable biomes,
and later tiers progressively swap in mythic and then cosmic vocabulary/
grammar, so "grander" means a genuinely different kind of name, not just
a bigger adjective in front of the same word.

Grammar (bands 1-5, "grounded" through "celestial"):
  - pure mode (one clearly dominant element): just that element's noun.
  - hybrid mode (top two elements close in weight): "{secondary adjective}
    {dominant noun}", e.g. air-secondary + earth-dominant -> "Windswept
    Canyon" - always a legible, describable place instead of two nouns
    mechanically stuck together.
Band 6 ("cosmic", tier 11+) drops the noun/adjective grammar entirely for
short poetic fragments per dominant element - geography stops making sense
at that scale.
"""

import math
import random

HYBRID_THRESHOLD = 0.2

# Each band holds, per element, a `noun` bank (used when that element is
# dominant - the head of the name) and an `adj` bank (used when that
# element is secondary - the modifier). Multi-word entries are fine; they
# compose the same way single words do.
VOCAB = {
    "grounded": {
        "fire": {
            "noun": ["Desert", "Volcanic Field", "Ashlands", "Lava Flats"],
            "adj": ["Scorched", "Smoldering", "Sunbaked", "Charred"],
        },
        "water": {
            "noun": ["Wetlands", "Marsh", "Tidal Flats", "Coral Reef"],
            "adj": ["Sodden", "Misty", "Brackish", "Reedy"],
        },
        "earth": {
            "noun": ["Canyon", "Highlands", "Stone Plateau", "Cavern"],
            "adj": ["Rocky", "Weathered", "Dusty", "Craggy"],
        },
        "air": {
            "noun": ["Windswept Plains", "Cloud Steppe", "Open Sky", "Highland Gale"],
            "adj": ["Windswept", "Breezy", "Airy", "Gusty"],
        },
    },
    "wild": {
        "fire": {
            "noun": ["Wastes", "Firelands", "Cinder Basin", "Scorchmark"],
            "adj": ["Molten", "Blazing", "Searing", "Ashen"],
        },
        "water": {
            "noun": ["Deep", "Drowned Basin", "Stormcoast", "Maelstrom"],
            "adj": ["Churning", "Drowned", "Storm-lashed", "Brimming"],
        },
        "earth": {
            "noun": ["Badlands", "Deepcave", "Ironridge", "Stonefall"],
            "adj": ["Jagged", "Iron-veined", "Crumbling", "Ancient"],
        },
        "air": {
            "noun": ["Stormfront", "Skybreak", "Galewild", "Thunderhead"],
            "adj": ["Howling", "Storm-torn", "Restless", "Wailing"],
        },
    },
    "elemental": {
        "fire": {
            "noun": ["Inferno", "Emberfield", "Pyreheart", "Cinderreach"],
            "adj": ["Undying", "Ravenous", "Roaring", "Living"],
        },
        "water": {
            "noun": ["Abysswell", "Tidereach", "Thundering Deep", "Krakenfen"],
            "adj": ["Fathomless", "Thundering", "Tideborn", "Ever-flowing"],
        },
        "earth": {
            "noun": ["Bedrock Expanse", "Rootdeep", "Ironheart", "Stoneforge"],
            "adj": ["Unshakable", "Living", "Rootbound", "Timeless"],
        },
        "air": {
            "noun": ["Skyreach", "Tempestborn", "Zephyrheart", "Cloudspire"],
            "adj": ["Tempestborn", "Ever-shifting", "Skybound", "Roaring"],
        },
    },
    "mythic": {
        "fire": {
            "noun": ["Cinderborn Expanse", "Emberfall Sanctum", "Pyrewild Reach", "Thronefire"],
            "adj": ["Cinderborn", "Emberkissed", "Sunforged", "Dragonfire"],
        },
        "water": {
            "noun": ["Leviathan's Rest", "Voidtide Trench", "Moonlit Fen", "Driftworld"],
            "adj": ["Voidtide", "Moonlit", "Leviathan-touched", "Timeworn"],
        },
        "earth": {
            "noun": ["Titan's Bones", "Worldroot Reach", "Ironcrown Depths", "Ageless Vault"],
            "adj": ["Titanborn", "Worldrooted", "Ironcrowned", "Ageless"],
        },
        "air": {
            "noun": ["Stormlord's Reach", "Skyveil Sanctum", "Windwalker's Rest", "Cloudrealm"],
            "adj": ["Stormwoven", "Skyveiled", "Windwalked", "Cloudborn"],
        },
    },
    "celestial": {
        "fire": {
            "noun": ["Starforge", "Sunwell", "Novaheart", "Solarium"],
            "adj": ["Starforged", "Sunbound", "Nova-lit", "Astral"],
        },
        "water": {
            "noun": ["Starwell", "Astral Tide", "Nebula Deep", "Everflow"],
            "adj": ["Starwoven", "Astral", "Nebulous", "Eternal"],
        },
        "earth": {
            "noun": ["Starstone Reach", "Astral Bedrock", "Worldheart", "Meteor Crown"],
            "adj": ["Starforged", "Astral", "Meteoric", "Worldbound"],
        },
        "air": {
            "noun": ["Starwind Reach", "Astral Skies", "Voidwind", "Cometrail"],
            "adj": ["Starwoven", "Astral", "Voidbound", "Comet-lit"],
        },
    },
}

BAND_ORDER = ["grounded", "wild", "elemental", "mythic", "celestial"]

# Band 6: geography stops making sense at this scale, so it's poetic
# fragments per dominant element instead of noun/adjective grammar.
COSMIC_TEMPLATES = {
    "fire": [
        "Where Embers Outlive Stars",
        "The Flame That Ate the Dark",
        "Ash Older Than Light",
    ],
    "water": [
        "Where the Tide Forgot Time",
        "The Deep Beneath All Deeps",
        "Where Silence Drowns",
    ],
    "earth": [
        "The Root Beneath Reality",
        "Stone Older Than the First Word",
        "Where Mountains Dream",
    ],
    "air": [
        "Where the Wind Remembers Nothing",
        "The Sky Beyond the Sky",
        "Silence Between Storms",
    ],
}

EMERGENT_THRESHOLD = 0.6
EMERGENT_QUALIFIERS = {
    "corruption": "Corrupted",
    "sanctity": "Sanctified",
    "arcane": "Arcane",
    "resonance": "Resonant",
}


def _band_for_tier(tier: float) -> str:
    step = math.floor(tier)
    if step <= 2:
        return "grounded"
    if step <= 4:
        return "wild"
    if step <= 6:
        return "elemental"
    if step <= 8:
        return "mythic"
    if step <= 10:
        return "celestial"
    return "cosmic"


def words_for_element(element: str) -> set[str]:
    """Every noun/adjective ever used for this element, across all bands."""
    words = set()
    for band in VOCAB.values():
        words.update(band[element]["noun"])
        words.update(band[element]["adj"])
    return words


def _dominant_and_second(weights: dict[str, float]) -> tuple[str, str, float, float]:
    full_weights = {el: weights.get(el, 0.0) for el in ("fire", "water", "earth", "air")}
    ordered = sorted(full_weights.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[0][0], ordered[1][0], ordered[0][1], ordered[1][1]


def _emergent_prefix(traits: dict[str, float]) -> str:
    top_trait, top_score = max(
        ((t, traits.get(t, 0.0)) for t in EMERGENT_QUALIFIERS), key=lambda kv: kv[1]
    )
    if top_score >= EMERGENT_THRESHOLD:
        return f"{EMERGENT_QUALIFIERS[top_trait]} "
    return ""


def compose_name(weights: dict[str, float], traits: dict[str, float], tier: float) -> str:
    dominant, second, dominant_share, second_share = _dominant_and_second(weights)
    prefix = _emergent_prefix(traits)
    band = _band_for_tier(tier)

    if band == "cosmic":
        return f"{prefix}{random.choice(COSMIC_TEMPLATES[dominant])}"

    vocab = VOCAB[band]
    if dominant_share - second_share >= HYBRID_THRESHOLD:
        base = random.choice(vocab[dominant]["noun"])
    else:
        adjective = random.choice(vocab[second]["adj"])
        noun = random.choice(vocab[dominant]["noun"])
        base = f"{adjective} {noun}"

    return f"{prefix}{base}"

"""Push tier as high as possible - 100% ratio on the previous result every
single step, 0% on the other three base environments - to climb as fast as
the formula allows and walk every tier band in one continuous run. This is
the cleanest possible probe of the naming system's band transitions: at
ratio=1.0 the tier formula degenerates to tier_n = n exactly (see the
assertion below), so every step lands on a whole-number tier and we get an
unambiguous, gap-free look at exactly what happens at each band boundary.

Writes a readable trace to tests/output/generation_ceiling.md so the
escalation (and where it gets rough - e.g. the numeral fallback firing
inside the cosmic band's poetic templates) can be reviewed directly.
"""

import random
from pathlib import Path

import pytest

from app.game_engine.environment_generator import World, generate_next_environment
from app.game_engine.naming import _band_for_tier

STEPS = 30
OUTPUT_PATH = Path(__file__).parent / "output" / "generation_ceiling.md"
BAND_SEQUENCE = ["grounded", "wild", "elemental", "mythic", "celestial", "cosmic"]


def test_maximum_dominance_climbs_tier_by_exactly_one_and_bands_stay_accurate():
    random.seed(0)
    world = World()
    lineage = world.get("fire")
    others = [world.get("air"), world.get("earth"), world.get("water")]

    rows = []
    seen_names: set[str] = set()
    previous_band_idx = 0

    for step in range(1, STEPS + 1):
        parents = [lineage, *others]
        child = generate_next_environment(parents, [1.0, 0.0, 0.0, 0.0], existing_names=seen_names)

        # Smoothness: at 100% dominance the tier formula (1 + ratio-weighted
        # parent tiers) degenerates to +1 flat every step - no jumps, no
        # drift. This is the fastest tier can possibly climb.
        assert child.tier == pytest.approx(float(step))

        # Accuracy: the band the generator's tier lands in must match
        # naming's own boundary function exactly, and must never regress
        # to an earlier, less-grand band as tier only ever grows.
        band = _band_for_tier(child.tier)
        band_idx = BAND_SEQUENCE.index(band)
        assert band_idx >= previous_band_idx
        previous_band_idx = band_idx

        assert child.name not in seen_names
        seen_names.add(child.name)

        top_emergent = max(
            (("arcane", child.traits["arcane"]), ("resonance", child.traits["resonance"]),
             ("corruption", child.traits["corruption"]), ("sanctity", child.traits["sanctity"])),
            key=lambda kv: kv[1],
        )  # fmt: skip
        rows.append(
            f"| {step} | {child.tier:.0f} | {band} | **{child.name}** | "
            f"{top_emergent[0]}={top_emergent[1]:.2f} |"
        )
        lineage = child

    report = [
        "# Maximum-dominance tier climb\n",
        "Every step combines the previous result at 100% ratio against the "
        "other 3 base environments at 0%, to climb tier as fast as possible "
        "and walk every tier band in one continuous run. `tier` is a whole "
        "number every step by construction (see the test).\n",
        "| Step | Tier | Band | Name | Strongest emergent trait |",
        "|---|---|---|---|---|",
        *rows,
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

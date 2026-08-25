# Procedural Environment Generation — Design

Status: **design only, not yet implemented.**

## Context

The environment-combination mechanic is the core of the game (combine the 4
active environments by how much time the monster spent in each → get a new
one), but the *result* is currently not actually generated —
`_name_from_library()` in `backend/app/game_engine/environment_generator.py`
picks the nearest match from a fixed, hand-authored list of 22 "gen-1"
prototypes in `backend/app/game_engine/prototypes.py`. Gen-2+ prototypes were
planned but never authored, so today the game can only ever produce those
same 22 outcomes, forever — there's no real progression or grandness. (Also
confirmed by investigation: gen-2+ blends currently get named essentially at
random from the gen-1 pool — a scoring bug, since with zero eligible
prototypes at their real generation, the softmax degenerates to uniform over
all 22.)

This replaces that with real procedural generation: the 4 base environments
(fire, air, earth, water) stay hardcoded as the roots, but everything
generated from combining them — name, and how "grand"/powerful it feels —
is computed from which environments were combined and in what ratio, with
grandness compounding the more a player leans into a lineage (e.g.
repeatedly generating fire-dominant results should eventually produce
something as grand as "sun's core"; mixing evenly across all 4 elements
should stay comparatively modest).

## Confirmed current state (informs the design)

- `Environment` dataclass: `name, weights (dict[str,float] — fractional
  ancestry back to the 4 base elements), traits (20-dim dict), generation
  (int), parents (list[str])`.
- `_compute_child_gen`: discrete, dominance-threshold based
  (`generation = max(parent_gens)+1`, or `dominant_gen+1` if one parent has
  >50% ratio and a lower generation).
- `_blend_weights`/`_blend_traits`: already continuous/procedural —
  ratio-weighted blending of parent weights and traits, with noise +
  amplification for anything above "gen 1". This math stays; only what's
  *driven by* generation changes to be driven by the new continuous tier.
- `_name_from_library`: the only truly "hardcoded" piece — nearest-neighbor
  match (cosine similarity + euclidean distance, softmax-sampled) against
  the fixed 22-entry `PROTOTYPE_LIBRARY`. This is what gets replaced
  entirely.
- DB schema (`KnownEnvironment`): `name, weights (JSONB), traits (JSONB),
  generation (Integer), parents (JSONB)` — no constraints on name content,
  safe to keep the shape (with `generation` becoming a float "tier").
- Client (`client/main.py`/`screens.py`): confirmed **zero hardcoded
  references** to any of the 22 prototype names. Unknown environment names
  already fall back gracefully to `hidden.png` for their background image.
  No client changes are required for this redesign.

## New design

### 1. Tier (grandness) — continuous, not discrete

Replaces `generation: int` with `tier: float`. Base environments
(fire/water/earth/air) have `tier = 0`. Formula:

```
child.tier = 1 + Σ_i (ratio_i × parent_i.tier)      for i in the 4 parents
```

i.e. one flat "+1" per combination, plus the ratio-weighted average of the 4
parents' own tiers. This is why it compounds with focus: if you keep picking
a high-tier fire-lineage result as the dominant (high-ratio) parent each
time, tier climbs roughly +1 per combination toward "sun's core" territory;
if you spread ratio evenly across low-tier/base parents, the weighted
average stays low and tier grows slowly. No separate "dominant streak
counter" is needed — the existing `weights`/ratio mechanism already encodes
lineage focus, this formula just makes tier respond to it directly and
continuously.

### 2. Trait blending — scale continuously with tier instead of switching on `generation == 1`

Today `_blend_traits`/`_blend_weights` are deterministic exactly at
`generation == 1` and noisy/amplified above it (binary switch). Replace with
continuous scaling by tier:

- `effective_sigma = BASE_TRAIT_SIGMA * sigma_scale(dominance) *
  growth(tier)`, `effective_amplification = AMPLIFICATION_FACTOR *
  growth(tier)`, `effective_emergent_drift = EMERGENT_DRIFT_SIGMA * tier`
  (already tier-scaled today via `child_gen`, keep the same shape).
- `sigma_scale(dominance)` (the existing per-combination "how decisive was
  this pick" factor) is unchanged — it still modulates noise based on
  *this* combination's ratio spread.
- `growth(tier)` is new: near 0 at `tier ≈ 1` (first-ever result stays
  close to deterministic, like today's gen-1) and increases with tier so
  high-tier results get visibly more extreme/characterful traits
  (temperature, radiation, volatility pushed toward their bounds; emergent
  traits — arcane/resonance/corruption/sanctity — become more prominent).
  A simple form like `growth(tier) = min(GROWTH_CAP, tier - 1)` clamped at
  0 is enough; exact constants are tuning, not architecture.

### 3. Procedural naming — fully algorithmic, no hand-curated per-tier name lists

Inputs: `weights` (fractional ancestry across the 4 base elements),
`traits`, `tier`.

**Step 1 — composition character.** `dominant` = element with max weight
share, `second` = runner-up. If
`weights[dominant] - weights[second] >= HYBRID_THRESHOLD` (e.g. 0.2):
**pure** mode (single dominant element). Otherwise: **hybrid** mode (blend
of the top two elements).

**Step 2 — base word.** Each of the 4 base elements gets a small, generic
word bank (not tied to any tier), e.g.:

| Element | Word bank |
|---|---|
| fire | Ember, Cinder, Blaze, Flame, Scorch, Magma, Pyre |
| water | Tide, Current, Depths, Mist, Brine, Torrent, Abyss |
| earth | Stone, Crag, Bedrock, Root, Vein, Ridge, Loam |
| air | Gale, Zephyr, Squall, Cloud, Vortex, Draft, Sky |

Pure mode picks one word from the dominant element's bank (weighted-random,
same `random` usage pattern as today). Hybrid mode combines the top two
elements' words via a small set of interchangeable patterns (e.g.
`"{secondary} {dominant}"`, `"{dominant} of {secondary}"`), picked randomly
for variety.

**Step 3 — tier epithet.** A single generic, reusable ladder (not
per-element, not hand-picked per specific name) applied by index: e.g.
`["", "Greater ", "Grand ", "Ascendant ", "Primordial ", "Celestial ",
"Transcendent "]`, indexed by `floor(tier) - 1` clamped to the ladder (so
the very first generated result, tier 1, gets no epithet — just the plain
element word, e.g. "Ember" — and epithets escalate from tier 2 up). Beyond
the ladder's length, append an escalating numeral suffix (e.g.
"Transcendent Ember II", "III", ...) so grandness never hard-caps.

**Step 4 — emergent qualifier (optional).** If any of the emergent traits
(arcane/resonance/corruption/sanctity) crosses a threshold (e.g. 0.6),
append a qualifier tied to the highest one (corruption → "Corrupted",
sanctity → "Sanctified", arcane → "Arcane", resonance → "Resonant").

**Step 5 — compose:** `f"{tier_epithet}{base_word}{emergent_suffix}"`.

This is deliberately reusable/generic vocabulary (4 short element word lists
+ one shared tier ladder + one emergent-qualifier map) rather than a large
per-tier-per-element authored table — it can express unlimited tiers without
ever running out, at the cost of not guaranteeing an exact evocative phrase
like "Sun's Core" will appear verbatim (that's the tradeoff of algorithmic
over curated naming, which is what was chosen here).

### 4. Data model changes

- `Environment.generation: int` → `Environment.tier: float` (rename;
  `BASE_ENVIRONMENTS` seed with `tier=0.0`).
- `KnownEnvironment.generation: Integer` → `KnownEnvironment.tier: Float` —
  new Alembic migration (column type change).
- `EnvironmentSchema.generation: int` → `EnvironmentSchema.tier: float` in
  `backend/app/schemas.py`.
- `backend/app/game_engine/prototypes.py`: remove `PROTOTYPE_LIBRARY`,
  `PROTO_NAMES`, `PROTO_VECS`, `PROTO_GENS`, the `_proto` helper — none of
  this is needed once naming is algorithmic. Keep `ALL_TRAITS`. New naming
  vocabulary (element word banks, tier ladder, emergent-qualifier map)
  lives in a new module, `backend/app/game_engine/naming.py`, separating
  "vocabulary data" from "generation algorithm" the same way
  `prototypes.py`/`environment_generator.py` were separated before.
- `backend/app/crud.py`: `_get_prototype_key`/`PROTOTYPES_BY_NAME` and the
  prototype-fallback branch inside `ensure_environment_known` are removed —
  with no prototype library, an unknown non-base name simply isn't known
  (this path shouldn't be hit in normal play, since `environment_slot_keys`
  only ever gets updated to names that were just generated and persisted in
  the same flow).

### 5. Clean slate for existing data

Only the 4 base environments are hardcoded going forward; all
previously-generated (non-base) `known_environments` rows are discarded,
not migrated — consistent with how local/dev save data has been treated as
disposable throughout this project. Any slot whose `environment_slot_keys`
or `hidden_environment_name` reference a non-base name gets reset back to
the 4 base defaults as part of rollout.

## Files touched (for the implementation pass)

- `backend/app/game_engine/environment_generator.py` — `_compute_child_gen`
  → `_compute_child_tier`; `_name_from_library` → new algorithmic naming
  call; tier-driven continuous noise/amplification.
- `backend/app/game_engine/prototypes.py` — strip prototype-matching data,
  keep `ALL_TRAITS`.
- `backend/app/game_engine/naming.py` — new: word banks, tier ladder,
  emergent-qualifier map, composition function.
- `backend/app/models.py`, `backend/app/schemas.py` — `generation` →
  `tier` (int → float).
- `backend/migrations/versions/` — new migration for the column type
  change.
- `backend/app/crud.py` — drop prototype-fallback logic in
  `ensure_environment_known`.
- `backend/tests/` — `test_environment_generator.py`/`test_prototypes.py`
  will need rewriting around tier math and naming composition instead of
  prototype-matching.
- No client changes required.

## Open tuning parameters (illustrative, not final)

`HYBRID_THRESHOLD`, the exact element word banks, the tier epithet ladder
and its length, emergent-trait thresholds, and `growth(tier)`'s exact shape
are all reasonable starting points, not locked-in values — expect to tune
these once the algorithm is actually running and namings can be eyeballed
in play.

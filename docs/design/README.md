# Design notes

## recipes.json

This is the design-time fitting record used to hand-tune the gen-1 environment
prototypes in `backend/app/game_engine/prototypes.py` (formerly
`prototypes_v4_fitted.py`). For each environment it records the parent
combination, mix ratios, generation, cosine similarity to its nearest
prototype, and whether it was an exact naming hit.

It is **not loaded by any runtime code** — it's a reference artifact kept for
whoever re-tunes the prototype library in the future.

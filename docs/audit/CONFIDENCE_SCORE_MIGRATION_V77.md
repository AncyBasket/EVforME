# Confidence migration → seed v77 (policy v2)

Base: main `4b491de` (seed v76). Source of Manus WIP: PR #33 (not merged).

## Scope

- Policy/scorer `scripts/catalog_confidence.py` (v2)
- Recalc + tests + docs
- Decode-only Swift: `confidenceScoreLegacy`, `confidencePolicyVersion`, `confidenceEvidence`
- Copy: “Data quality” / “Qualità dati” (not probability)

## Out of scope

- PHEV formulas / electric share / derived range
- API code, privacy, deploy
- Technical vehicle values, `fieldSources` / `fieldSourceDates` content
- PR #33 other threads

## Technical integrity

- Rows: 6977 unchanged set
- Technical fingerprint (all keys except confidence*): identical before/after
- Model 3 IT 2026 ×4: technical fields identical to main; score metadata only updated

## Score distribution (after v2)

See `recalculate_catalog_confidence.py` preview on this branch. Notable change vs pre-migration: **no 0.95 “exact match and dated” tier** — non-empty sources/dates + `officialMatched` no longer invent documentary verification.

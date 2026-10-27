# EV variant readable labels — design

**Branch:** `fix/ev-variant-labels` from `main` @ `509260c` (#24)  
**PR:** DRAFT; no App Store bump; do not touch `feature/review-safety`  
**Rule:** no invented data; every commercial name / official kW / battery needs an official OEM URL.

## Goal

Replace opaque EEA-kW titles (e.g. “42 kW”) with manufacturer trim names when a verified 1:1 match exists; otherwise “Versione n” + small EEA homologation note. Drop groups whose EEA kW exceeds model max official power by >5 kW.

## Tesla / dual-motor (approved: A)

Label uses official trim name + **system** max power when the OEM sheet states it; otherwise F+R sum **only if both axle powers appear on the same official page**. Matching may still use axle-level kW (±5) against EEA when that is how EEA filed the record.

## Audit set

- Top 40 BEV model/years by EU registrations (sum of group `n` in current refs).
- Plus every parent with ≥6 version groups.
- List + registration counts in the ref.

## Official sources (allowed)

Manufacturer sites, OEM press kits, official technical PDFs for that model **year**.  
**Forbidden:** ev-database, Wikipedia, magazines, aggregators.

Per model/year store: URL, list of `{name, power_kw_max, wltp_range_km?, battery_kwh?, awd?}`.

## Matching

One EEA group ↔ one official version:

- Official WLTP range ∈ [EEA min, EEA max] with ±3% tolerance on bounds, **or**
- EEA group kW within ±5 of official max (or axle power used for match under rule A),
- Plus traction when known.

Ambiguous (two officials fit one group, or two groups claim one official) → leave unmatched.

## Labels & mutations

| Case | Title | Subtitle | Calc |
|------|-------|----------|------|
| Matched | `<official name> · <official kW> kW` | Autonomia WLTP min–max (EEA) | prudent EEA min Zr / max Wh |
| Unmatched / outside audit | `Versione <n>` | Autonomia… + small “Potenza omologata EEA … (può differire…)” | same |
| Two groups → same official | Merge; recompute min–max from union of EEA records | | |
| EEA kW > model max official +5 | Drop; reason in ref | | |
| Battery | Only if same official source+year | | |

## Migration

United/removed version ids: never silent substitute to a different trim. Alias old→new **only** if the old group’s EEA records are a subset of the new merged group; else user re-picks (#21/#24).

## Must-fail / tests / merge gate

As in user request §3–6. Merge squash only if green, no unsourced commercial/official fields, and **≥30 of the top 40** have an official source found.

## Seed

`seedVersion` → 61.

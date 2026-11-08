# PHEV logic recovery from PR #33 (selective)

Base: main `71d6f5d` (seed **v77**). WIP reference: `05c22b9` / PR **#33** (preserved).

## Investigation (main vs #33)

| Point | Main | #33 WIP | This PR |
|---|---|---|---|
| Fallback 50 km in `phevElectricKmShare` | `wltpRangeKm ?? 50` | Removed; uses `resolvedPHEVElectricRangeKm ?? 0` then **10% floor** | Removed; **no substitute**. Missing range → no share / no verdict |
| Range from battery÷CD | Share: no. Weekly charges: yes (generic energy) | Shared helper; weekly uses CD-only derive | Derive = **labeled estimate only**; never unlocks verdict or replaces catalog range |
| Min electric share 10% | Always `max(0.1, raw)` | Same floor when range missing | **No artificial floor**. Share from range + habits; upper ICCT cap 0.6 kept when range known |
| Verdict with missing calc fields | CS+CD gated; range not gated | Same + note when range missing | Gate also on **usable electric range** (catalog or user override) |

## Recover from #33

| Change | Why |
|---|---|
| Drop silent 50 km fallback | Matches “no silent conventional substitute” |
| Align PHEV weekly range away from weighted/generic energy | Avoid inconsistent / blended energy paths |
| L10n note that missing range is not inventable | Honesty (used when estimate shown, not as unlock) |
| Regression test that missing range ≠ invented 50 km | Lock the fix |

## Discard from #33

| Change | Why |
|---|---|
| 10% floor as stand-in for missing range | Artificial minimum electric share |
| Verdict still computed with only the 10% floor | Violates fail-closed |
| `ConfidenceEvidence` schema / confidence wiring | Already on main via #35; out of scope |
| `VehicleCatalogService` manifest seedVersion | Not PHEV formulas |
| Catalog JSON / Python PHEV-network scripts | Data already recovered in #34; seed stays v77 |
| Privacy / low-confidence note wiring | Other thread |
| CNG hygiene assertion tweaks | Unrelated |

## Required behavior (this PR)

1. No missing datum replaced with a conventional default.
2. No pure-electric kWh invented from weighted, battery, or range.
3. Ask only for calc fields that are actually missing; keep valid ones.
4. No verdict / conclusive savings until required data are present and valid.
5. Electric share depends on explicit range + habits; no artificial minimum.
6. Intermediate derived range (battery÷CD) may be shown as **estimate** only — never written to seed, never used to bypass the gate.

## Follow-up on #36 head `8de92ae`

- Invalid but positive overrides (e.g. 1 kWh/100, 2.5 L/100 CS) must keep the field editable (`VehicleCalcDataGate`).
- Shared sufficiency gate for prompt, €/km preview, and verdict — incomplete/invalid PHEV preview is **n/d**, not a partial total.

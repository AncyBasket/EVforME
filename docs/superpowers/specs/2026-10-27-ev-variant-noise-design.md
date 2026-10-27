# EV variant noise cleanup — design

**Branch:** `fix/ev-variant-noise` from `main` @ `52d4d35`  
**PR:** DRAFT; no App Store bump; do not touch `feature/review-safety`  
**Rule:** no invented versions / ranges / kW.

## Problem

Some model/years show impossible EEA version groups (e.g. Ioniq 5 N 2023 → 11 groups shared with Ioniq 5; Dacia Spring 2023 → 11; Model Y 2023 → 17). Causes: base Cn absorbed by sport trims (and vice versa), low-registration noise, wrong/non-official EEA `ep_KW`.

## Matching (approved: option B + exclusive pools)

### Pass 1 — Cn / family, exclusive

1. Detect catalog **sibling pairs**: same brand + year where one model’s merge-key is a strict prefix of another’s (e.g. `IONIQ5` ⊂ `IONIQ5N`, `MODELY` ⊂ `MODELYPERFORMANCE`), or known sport tokens as longer catalog names (`N`, `Performance`, `RS`, `GRMN`, …) when they exist as separate seed rows.
2. **Specific** parents claim only EEA Cn keys that match their own merge-key / same-model-variant expansion of that key — **not** the shorter base key by fuzzy fallback.
3. **Base** parents claim base family Cn keys, then **drop any atomic EEA record** already claimed by a specific sibling for that year.

### Pass 2 — sport trim without own Cn (rule B)

When a specific parent has no dedicated EEA Cn (e.g. no `IONIQ5N` in 2023):

1. Load **official manufacturer powers** for that model/year (scheda / listino). Store URL(s) in the ref. Multiple official figures allowed (e.g. Ioniq 5 N normal + N Grin Boost); the one that matches an EEA record (±5 kW) wins.
2. Candidates = atomic EEA records of the **base** model/year whose `ep_KW` is within ±5 of any official power.
3. If ≥1 candidate: build **at most one** group (existing kW±5 + traction clustering on those candidates only). Range/Wh **only** from those EEA records. Remove those records from the base pool (no shared records).
4. If 0 candidates: **zero** groups; parent keeps no EEA version autonomy (“autonomia non disponibile”); invent nothing.

PR lists every sport-trim parent: `1 group (kW, source URL)` or `0 (reason)`.

## Noise filter

Keep a group only if:

- `registrations >= 0.02 * sum(registrations of all groups for that parent before noise filter)` **OR**
- `registrations >= 200`

Thresholds written in the ref (`minShareOfParent: 0.02`, `minAbsoluteRegistrations: 200`). Dropped groups listed in the ref with reason `below_registration_threshold`.

Apply after matching/clustering, before writing children. Sport rule-B single groups are also subject to the threshold unless registrations meet it (if the only official match is tiny, drop → 0 groups; do not invent).

## Official kW audit

For:

- the **30** BEV model/years with highest EU registrations (sum of group n after matching, before or after noise — use after matching, before noise for ranking), and
- every parent that still has **>6** groups after noise,

compare each remaining group’s representative kW to the official manufacturer power list for that model/year (±5). URL in ref.

- Group kW matches no official power → drop; reason `kw_not_on_official_sheet` in ref.
- No official source found → **keep** the group; list in PR as `unverified_official_kw` (do not invent powers).

Merge gate: no parent with **>8** groups unless an official source justifies that many distinct powers.

## Seed / refs / aliases

- Bump `seedVersion` only if existing pipeline requires it for catalog change; **no App Store marketing bump**. Prefer seedVersion +1 if seed bytes change (follow prior PRs: seed v59 → v60).
- Refs: thresholds, discarded groups + reasons, official URLs, sport-trim outcomes, dual-claim resolutions.
- `ev_variant_single_aliases.json`: only parent → sole child when exactly one version remains. **Never** alias a removed version id to another version (PR #21 / #23: unavailable → user re-picks).

## Must-fail (`check_ev_variants.py`)

1. `hyundai-ioniq-5-n-2023` with more than 1 group.
2. `dacia-spring-2023` with more than 2 groups.
3. Any kept group below registration threshold.
4. Any EEA record identity used by two different parent models.

`PYTHONHASHSEED` 0–5 → identical output.

## Migration

Removed version ids: `resolveId` → nil → empty target / explicit choice; no silent substitute. Same as PR #21.

## Tests / PR / merge

- One simulator; parallel testing OFF; max concurrent destinations 1.
- Wait if `pgrep -fl xcodebuild`.
- Unit ≥274 / Swift Testing ≥1 / UI ≥17; all green, none skipped.
- DRAFT PR comment: HEAD, test counts, script output, BEV MY with range (460 → after), versions (1513 → after), distribution + top 10, top 10 “kW groups vs official + source”, sport-trim 0/1 table, dual-claim resolutions.
- Undraft + squash merge **only if** all green **and** no model >8 versions without official justification; else report gaps, no merge.

## Out of scope

- App Store version bump.
- `feature/review-safety`.
- Inventing EEA rows or OEM kW without a cited URL.

# EV variant noise cleanup — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove impossible EV version groups via exclusive EEA matching, registration noise filter, and official-kW checks; ship as DRAFT PR `fix/ev-variant-noise`.

**Architecture:** Extend `scripts/build_ev_variants_from_eea.py` (+ small helpers) to assign EEA records exclusively across base/sport siblings, apply 2%/200 noise, audit kW against a curated official-power table with URLs; tighten `check_ev_variants.py` must-fails; rebuild seed/refs/aliases; migration already forces re-pick on removed ids.

**Tech Stack:** Python 3 build/check scripts, JSON seed/refs, XCTest / Swift Testing / UITests.

## Global Constraints

- Branch from `main` @ `52d4d35`; do not touch `feature/review-safety`.
- No App Store bump; no invented data.
- Thresholds: `minShareOfParent=0.02`, `minAbsoluteRegistrations=200`, kW tol ±5.
- Tests: 1 sim, parallel OFF; ≥274 / 1 / 17 all green.
- Merge squash only if green and no parent >8 groups without official source.

---

### Task 1: Branch + exclusive matching + sport rule B

**Files:** `scripts/build_ev_variants_from_eea.py`, optional `scripts/ev_variant_official_kw.json` (OEM powers + URLs)

- [ ] Create `fix/ev-variant-noise` from `main`.
- [ ] Implement sibling detection + exclusive Cn/record pools.
- [ ] Sport without Cn: match official kW ±5 → ≤1 group; claim records from base; else 0.
- [ ] Record dual-claim resolutions + sport outcomes in build report/ref.

### Task 2: Noise filter + official kW audit

- [ ] Drop groups below 2% parent share and <200 n; list in ref.
- [ ] For top-30 BEV MY + parents with >6 groups: drop groups not on official sheet; keep + flag if no source.
- [ ] Rebuild seed (v60), refs, CDN note, single aliases (only true singles).

### Task 3: check_ev_variants must-fails + hashseed

- [ ] Add must-fails: ioniq-5-n-2023 ≤1; spring-2023 ≤2; no below-threshold kept; no shared EEA record across parents.
- [ ] Confirm PYTHONHASHSEED 0–5 identical.

### Task 4: Migration sanity + unit coverage

- [ ] Confirm removed version ids are not aliased to other versions.
- [ ] Extend `EVVariantsTests` for thresholds / exclusivity where practical.

### Task 5: Full test suite + DRAFT PR

- [ ] Wait for xcodebuild; run full suite 1 sim parallel OFF.
- [ ] Open DRAFT PR with required comment numbers; merge only if gate passes.

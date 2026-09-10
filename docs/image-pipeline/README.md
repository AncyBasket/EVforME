# Free vehicle image pipeline (CC0 / Public Domain)

Zero-budget, commercial-safe photos for a **shortlist** of Italy-relevant vehicles.
The rest of the catalog keeps editorial placeholders (`VehicleHeroImage`).

## Non‑negotiable rules

**Forbidden:** Quattroruote / Edidomus, generic Unsplash, dealer scraping, catbox,
paid imagery APIs, AI renders of specific marques/models.

**Allowed:** verified **CC0** or **Public Domain** only (v1). No CC-BY / CC-BY-SA
(in-app attribution is a separate project).

**Do not** touch Apple Developer / Archive / ASC from this pipeline.

## Phase A — top IT targets

```bash
python3 scripts/build_top_it_image_targets.py
```

Writes `docs/image-pipeline/top_it_targets.json` (~220 rows).

### How the list is chosen

1. Start from `EVforME?/Data/vehicles.seed.quality.json` (~8.4k rows).
2. Keep brands familiar on the Italian market (Fiat, Jeep, Alfa Romeo, VW, Toyota,
   Renault, Peugeot, Ford, BMW, Mercedes-Benz, Audi, Opel, Hyundai, Kia, Tesla,
   Skoda, SEAT, Cupra, … — see `PRIORITY_BRANDS` in the script).
3. Keep model years **≥ 2018**.
4. Collapse to **one id per (brand, model, powertrain)** — newest year wins.
5. Rank by brand priority, then year, with a small EV/PHEV boost.
6. Cap **max 16 models per brand**, then take the top **N** (default 260) so
   Audi / Mercedes / Hyundai / Kia / Tesla / … appear alongside Fiat / VW.

This is a *search shortlist*, not a claim that every row will get a photo.

## Phase B — CC0/PD search

```bash
# Slow + resume-safe. Prefer Openverse CC0 first:
python3 scripts/search_free_vehicle_image_candidates.py --openverse-only --sleep 0.9

# Optional Commons pass (CC0/PD via extmetadata):
python3 scripts/search_free_vehicle_image_candidates.py --sleep 1.0
```

Writes `docs/image-pipeline/candidates/<vehicle-id>.json`:

- `approved`: **false** by default
- `candidates[]`: `url`, `license`, `author`, `source_page`, `query`, `match_score`
- Doubtful brand/model match → candidate omitted (`match_score` gate)

Sources: [Openverse](https://api.openverse.org/) `license=cc0`, Wikimedia Commons API
with license filter. On rate-limit: increase `--sleep`, re-run (skips existing files).

## Phase C — controlled apply

```bash
python3 scripts/apply_free_vehicle_images.py --dry-run
python3 scripts/apply_free_vehicle_images.py
```

Only files with `approved: true` and license ∈ {cc0, pd, public domain} update
`imageURL` in the quality seed. Everything else stays `null`.
On write: bumps `seedVersion` in `VehicleCatalogService.swift` and refreshes
`ATTRIBUTION.md` (internal provenance, not shown in UI).

## Phase D — UI

`VehicleHeroImage` loads HTTPS `imageURL` via `VehicleImageLoader` (memory cache).
Failure or blocked host → editorial placeholder (no crash, no blank hero).
Risky hosts (Edidomus, Quattroruote, Unsplash source, catbox) stay blocked.
**Wikimedia / Flickr (via Openverse)** are allowed when the URL was applied through
this pipeline.

## Manual approval

Edit a candidate JSON:

```json
"approved": true,
"preferred_url": "https://…"
```

Approve only when brand + model are obvious in title/filename/source page.

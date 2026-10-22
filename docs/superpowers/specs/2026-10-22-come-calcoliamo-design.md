# Come calcoliamo / How we calculate — design

**Branch:** `feature/come-calcoliamo` (from `main` @ 281436d)  
**Decision:** explain **both** vehicles (source + target).

## Goal

A trust screen that shows where each chosen car’s numbers come from, using the **same constants/functions** as the live calculation (no hardcoded display numbers).

## Screen

`HowWeCalculateView` — scrollable sheet/page, IT/EN via Localizable.

For **each** of source and target:

1. **Consumption** — catalog `sourceName` (+ tappable URL if present); confidence as Alta/Media/Bassa from `confidenceScore` bands (≥0.8 / ≥0.5 / else); if `energyIsWeighted`, show existing weighted-energy note.
2. **CO₂ → L/100** — when fuel was derived from CO₂ (detect via source text / catalog convention); show Reg. (EU) 2017/1151 Annex XXI Sub-Annex 7 factors from a new Swift `FuelFromCO2Constants` (values moved from `scripts/fill_catalog_fuels_from_eea.py`); EUR-Lex link.
3. **Road tax (bollo)** — formula text; regional €/kW from `ItalianRegion` APIs; national estimate note when region has no own tariff; EV exemption years + ¼ after; superbollo threshold/rate from `ItalianRegion.nationalSuperbolloEUR`.
4. **Fuel & electricity prices** — MIMIT / Eurostat as used in code; user can override sliders.

Shared facade: `HowWeCalculateExplainer` (pure) builds view models from `VehicleCatalogItem` + `UserInput` + region — UI only renders strings/numbers from that model.

## Navigation

- VerdictView: toolbar/link “Come calcoliamo”
- GuidesHubView: list entry like other guides

## Chargers on verdict

Prominent “Colonnine vicino a te” → `ChargingMapView` with `preferDeviceLocation: true`. Denied → clear message + Open Settings; city search still available. Radius 30 km unchanged. Privacy copy + `NSLocationWhenInUseUsageDescription` aligned (on-device / Apple Maps only).

## Tests & smoke

- Unit: Molise/Lazio/Lombardia displayed €/kW == calculation helpers; CO₂ factors == script constants; confidence bands.
- Smoke shots: how-we-calculate screen + verdict chargers button (portrait, no EXIF Orientation 6).

## Out of scope

App version bump, CDN upload.

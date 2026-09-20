# Smoke 1.1 + 1.2 + 1.3 — iOS Simulator

**Date:** 20 September 2026  
**Base:** `b4d8d2f` (+ blocker fix for last-comparison refresh)  
**Destination:** iPhone 17 Pro (`B3F4929C-7F76-49A4-B87F-27EFD81F9CD3`) · **iOS 27.0**  
**Xcode:** `/Applications/Xcode.app`  
**Method:** `EVforME?UITests/SmokeProductUITests` + screenshots in `docs/smoke/shots/`  
**Unit suite:** `EVforME?Tests` — **84** tests, 0 failures (post-fix)

## Summary

| Area | Result | Notes |
|------|--------|-------|
| Cold launch / workshop | ✅ | Preset Golf → Model 3; CTA “Dimmi la verità” |
| **1.1 Retention** | ✅ | Ultimo confronto + Riapri / Ricalcola / Ripristina; notification prompt dismissible (“Non consentire”) |
| **1.2 Kit Italia** | ✅ | Incentive “Se compro entro …”; bollo/assic/manutenzione + disclaimer; Guides bollo |
| **1.3 Colonnine** | ✅ | Guides entry → map sheet; city “Milano” → pin (Fastway) + Apri in Mappe + disclaimer |
| Regression | ✅ | Tabs Banco ↔ Letture; sheet dismiss OK; no crash |
| Free / no Store | ✅ | No Archive / TestFlight / ASC in this smoke |

## Checklist

### Cold launch
- [x] App starts on Simulator
- [x] Workshop usable offline / with live refresh best-effort
- [x] Shot: `01_workshop_cold.png`

### 1.1 Retention
- [x] Simulate → Verdict
- [x] Optional notification prompt does not crash (deny OK)
- [x] After dismiss, **Ultimo confronto** card on Banco
- [x] **Ricalcola con dati di oggi** reopens verdict
- [x] **Ripristina nel form** / **Riapri verdetto** work
- [x] Shots: `04_last_comparison_card.png`, `05_verdict_recalculated.png`

### 1.2 Kit Italia
- [x] Verdict costs section: bollo / assicurazione / manutenzione ICE vs EV + disclaimer
- [x] Incentive window copy on card (“Se compro entro 31 dic 2026”)
- [x] Guides: “Bollo ed esenzioni EV (orientativo)”
- [x] Shots: `02_verdict_open.png`, `03_verdict_kit_italia.png`, `07_guides_bollo.png`

### 1.3 Colonnine
- [x] Guides → **Colonnine vicino a te**
- [x] City mode Milano → map pins or honest empty + Apri in Mappe
- [x] Disclaimer visible
- [x] Shots: `06_guides_hub.png`, `08_charging_map_sheet.png`, `08_charging_map_city.png`, `08b_charging_map_fallback.png`

### Regression
- [x] Onboarding skip / open bench OK (`UITEST_PRESET_VEHICLES=1`)
- [x] Tab switch without freeze
- [x] Dismiss map / verdict without crash

## Blocker found & fixed (product)

**Issue:** After first verdict, `InputView` stayed mounted under the sheet; `onAppear` did not re-run, so **Ultimo confronto** stayed hidden until a later remount.  
**Fix:** `ScenarioHistoryStore.save` posts `.evScenarioHistoryDidChange`; `InputView` refreshes on that notification.  
**Also:** skip StoreKit review prompt when `UITEST_PRESET_VEHICLES=1` (smoke stability only).

## How to re-run

```bash
# Units
xcodebuild test -project "EVforME?.xcodeproj" -scheme "EVforME?" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0' \
  -only-testing:"EVforME?Tests"

# Smoke UI (shots land in docs/smoke/shots via #filePath)
xcodebuild test -project "EVforME?.xcodeproj" -scheme "EVforME?" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0' \
  -only-testing:"EVforME?UITests/SmokeProductUITests"
```

## Shots index

| File | What |
|------|------|
| `01_workshop_cold.png` | Banco cold |
| `02_verdict_open.png` | Verdict (+ optional system prompt) |
| `03_verdict_kit_italia.png` | Bollo / assic / manutenzione |
| `04_last_comparison_card.png` | Ultimo confronto 1.1 |
| `05_verdict_recalculated.png` | After ricalcola |
| `06_guides_hub.png` | Colonnine entry + bollo row |
| `07_guides_bollo.png` | Scheda bollo |
| `08_charging_map_sheet.png` | Map sheet |
| `08_charging_map_city.png` | Milano + pin |
| `08b_charging_map_fallback.png` | Map / Apri in Mappe state |

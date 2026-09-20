# EVforME?

iOS app that helps decide whether switching to an EV fits your yearly kilometers, charging setup, and price assumptions.

## Features

- **1.1 retention loop**: card “Ultimo confronto”, ricalcolo con dati live + delta prezzi/incentivi, reminder locali soft a 30/90 giorni (permesso solo dopo il primo verdetto)
- **Workshop bench**: yearly km, fuel/electricity prices, ownership years, urban vs mixed driving, home charging, ICE → EV pair from a large catalog
- **Verdict**: `yes` / `maybe` / `notYet` with cost reasons, 5-year chart, fear vs reality, scenario chips
- **On-device AI explanation** (Foundation Models / Apple Intelligence when available)
- **App Intents / Shortcuts**: simulate EV suitability; open last verdict
- **Home Screen widget**: last verdict via App Group
- **Liquid Glass** chrome on masthead, tabs, and verdict panels (honors Reduce Transparency)
- **IT / EN** localization

## Architecture (high level)

```
EVforME?/
├── App/                 # Entry, shell, App Intents
├── Core/Models + Logic  # Simulator, validator, catalog, storage, AI, widget snapshot
├── Features/            # Onboarding, Verdict, Education, Debug
├── UI/                  # Theme, glass, components
└── Utils/               # L10n, formatters, share text
EVforMEWidget/           # WidgetKit extension
```

## Requirements

- Xcode recente (Xcode 16+; Xcode 26/27 ok per SDK Liquid Glass / Foundation Models)
- Deployment target **iOS 17.0** (app, widget, tests)
- Optional local API on `127.0.0.1:8787` in **Debug** only (`Defaults.swift`); Release uses bundled seed + costs
- **Free** — no IAP / paywall
- Live refresh on every cold start and foreground: energy costs (MIMIT/Eurostat) + IT incentives (bundle / optional `EVFORME_INCENTIVES_URL`) + catalog (optional CDN)

## Tests

```bash
# Prefer iOS 17 sim if installed; otherwise any ≥17 (e.g. 18.6)
xcodebuild test -scheme 'EVforME?' \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=18.6' \
  -only-testing:'EVforME?Tests' \
  -parallel-testing-enabled NO
```

## Notes

- Input field `dailyKm` is **kilometers per year** (historical name).
- `areaType` adjusts ICE/EV consumption multipliers and charge frequency.
- Catalog expansion to 4000+ synthetic rows runs only in **DEBUG**.
- Liquid Glass / on-device AI explanation require iOS 26+; on iOS 17–25 the app uses elevated surfaces and L10n fallback explanations.
- 1.0 ships **placeholder** vehicle heroes only (no remote photos).

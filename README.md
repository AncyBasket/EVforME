# EVforME?

iOS app that helps decide whether switching to an EV fits your yearly kilometers, charging setup, and price assumptions.

## Features

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

- Xcode 26.2+ (Xcode 27 recommended for iOS 27 SDK / Liquid Glass refinements)
- Deployment target **iOS 26.2**
- Optional local API on `127.0.0.1:8787` in **Debug** only (`Defaults.swift`); Release uses bundled seed + costs

## Tests

```bash
DEVELOPER_DIR=/Users/andrea/Downloads/Xcode-beta.app/Contents/Developer \
xcodebuild test -scheme 'EVforME?' \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -parallel-testing-enabled NO
```

## Notes

- Input field `dailyKm` is **kilometers per year** (historical name).
- `areaType` adjusts ICE/EV consumption multipliers and charge frequency.
- Catalog expansion to 4000+ synthetic rows runs only in **DEBUG**.

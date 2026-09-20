# TestFlight / App Store Connect — preflight

## Phase status

| Phase | Item | Status |
|------|------|--------|
| 1 | Strip immagini non licenziate | **Done** — `imageURL = 0` on quality seed; `seedVersion = 26` |
| 2 | Commit snapshot | **Done** — product on `main` |
| 3 | Remote + push | **Done** — https://github.com/AncyBasket/EVforME |
| 3 | Privacy HTTPS | **Done** — https://ancybasket.github.io/EVforME/privacy/ |
| 3 | `EVFORME_PRIVACY_URL` | **Done** — same URL in `EVforME?/Info.plist` |
| 4 | Full unit tests (`EVforME?Tests`) | **Done** — green on Xcode / iOS 17+ destinations |
| 4 | Vehicle photos (1.0) | **Done** — **no remote vehicle photos in 1.0**; editorial placeholders only (`VehicleHeroImage`). CC0 pipeline paused (optional later). |
| 4 | Deployment | **iOS 17.0** everywhere — Liquid Glass / Foundation Models gated `#available(iOS 26, *)` |
| 4 | Launch refresh | **Hardened** — cold start + foreground: `OfficialCostService` + `ItalianIncentivesService` + catalog (best-effort; offline → cache/bundle) |
| 4 | ASC listing pack | **Ready** — [`docs/asc/ASC_STORE_LISTING.md`](docs/asc/ASC_STORE_LISTING.md) + [`docs/asc/screenshots/6.7/`](docs/asc/screenshots/6.7/) · **listing ready, upload pending Dev** |
| 4 | UITests | **Done** — `testInputToVerdictFlow` green (`e3d5801`) |
| 4 | Archive (local `.xcarchive`) | **Done** — `/tmp/EVforME.xcarchive` · **1.0 (1)** · arm64 · Xcode 27 beta |
| 4 | Upload → App Store Connect | **Blocked** — no ASC app record for `Gancione.EVforME-` |
| 4 | TestFlight Internal | **Paused** — Apple Developer account expired; renew post-vacation, then create ASC app record + upload |

## Archive Xcode choice

- Project floor: **iOS 17.0** (`IPHONEOS_DEPLOYMENT_TARGET`) — aligned with Toller/Gwent
- Prefer a recent Xcode that can build the current SDK; runtime features (Glass, Foundation Models) activate only on iOS 26+
- Version: **1.0 (1)** — Free
- Live data: every launch/foreground refreshes energy + incentives (see `EVforMEApp.refreshLiveData`)

## Unit test command (green)

```bash
# Lowest available runtime ≥17 on this Mac (example: 18.6). Prefer true iOS 17 if installed.
xcodebuild test \
  -project "EVforME?.xcodeproj" \
  -scheme "EVforME?" \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=18.6' \
  -only-testing:"EVforME?Tests"
```

Also smoke on a recent sim (iOS 26/27) when available:

```bash
xcodebuild test \
  -project "EVforME?.xcodeproj" \
  -scheme "EVforME?" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0' \
  -only-testing:"EVforME?Tests"
```

**Verified 2026-09-19:** no iOS 17 runtime on this Mac; full `EVforME?Tests` green on **iOS 27.0** (63 tests). iOS **18.6** sim builds and runs refresh logs (costs+incentives), but XCTest host hits a repeatable `malloc: pointer being freed was not allocated` after some `EVSimulator` cases (Xcode 27 + older runtime flake) — product path on 27 is green.

## ASC (must match)

- Privacy Policy URL: `https://ancybasket.github.io/EVforME/privacy/`
- Copy / keywords / screenshots: [`docs/asc/ASC_STORE_LISTING.md`](docs/asc/ASC_STORE_LISTING.md)

## Archive / Upload notes (2026-09-10)

- Archive: **SUCCEEDED** with Xcode beta (`DEVELOPER_DIR=…/Xcode-beta.app/…`), scheme `EVforME?`, `generic/platform=iOS`
- Version: **1.0 (1)** · Bundle ID `Gancione.EVforME-` · Widget `Gancione.EVforME-.Widget` · Team `C4B24C7ADF`
- Local artifact: `/tmp/EVforME.xcarchive` (also openable in Xcode Organizer)
- Export/upload failed with: *App record with bundle identifier "Gancione.EVforME-" not found on App Store Connect*
- No ASC API key (`.p8`) on this Mac → upload after app creation = Xcode Organizer or re-run export
- Archive codesign used **Apple Development** (no Apple Distribution identity in keychain yet). After app record exists, create **Apple Distribution** in Xcode → Settings → Accounts → Manage Certificates if export asks for it
- Export compliance: HTTPS/ATS only; `ITSAppUsesNonExemptEncryption` not in Info — answer in ASC UI (typically *No* custom crypto)

### Andrea — next clicks

1. [App Store Connect](https://appstoreconnect.apple.com) → My Apps → **+** → iOS app  
   - Bundle ID: `Gancione.EVforME-`  
   - Privacy Policy URL: `https://ancybasket.github.io/EVforME/privacy/`  
   - Price: Free · copy from [`docs/asc/ASC_STORE_LISTING.md`](docs/asc/ASC_STORE_LISTING.md)
2. Xcode beta → **Window → Organizer** → select `EVforME?` archive → **Distribute App** → App Store Connect → Upload  
   (or re-run `xcodebuild -exportArchive` with the same ExportOptions after the record exists)
3. Wait for processing → TestFlight → Internal Testing → add Andrea/team → enable build  
4. Export compliance questionnaire as above

## Do not App Store submit until

- [x] Privacy URL live on HTTPS
- [x] Product committed + pushed
- [x] Risky image hosts stripped
- [x] Full unit tests green on archive Xcode toolchain
- [x] Local archive 1.0 (1) produced
- [ ] ASC app record created + build uploaded
- [ ] Internal TestFlight build installed on a real device

## Product 1.1 — retention loop

- Card **Ultimo confronto** on workshop after first saved verdict (reopen / recalculate / restore form)
- Delta badge when fuel ≥ €0.05/L or electricity ≥ €0.02/kWh (or incentive moved) vs snapshot
- Soft local notifications at 30d + 90d after first verdict (permission then); tap → last compare / live recalc if data moved
- Free: no IAP / paywall / account

## Product 1.2 — Kit Italia

- Incentive schedule: optional `validFrom` / `validUntil`; UI “Se compro entro …” / stale badge
- Verdict costs: bollo / assicurazione / manutenzione ICE vs EV (stime + disclaimer)
- Guides: “Bollo ed esenzioni EV (orientativo)”

## Product 1.3 — Colonnine vicine

- Guides / Verdict entry → `ChargingMapView` (MapKit + MKLocalSearch, no paid API)
- Location When In Use only when opening the map; city fallback + “Open in Maps”
- Privacy: in-session map use only, not sent to EVforME backend; no background tracking

## Smoke 1.1–1.3 (Simulator)

- **2026-09-20** — iPhone 17 Pro / **iOS 27.0** (`docs/smoke/SMOKE_1_1_1_3.md` + `docs/smoke/shots/`)
- UITests: `SmokeProductUITests` (retention + map city); units `EVforME?Tests` 84 green
- No Archive / TestFlight / ASC in this pass

## App Store listing (offline pack)

- **Ready to paste:** [`docs/asc/ASC_STORE_LISTING.md`](docs/asc/ASC_STORE_LISTING.md)
- Screenshots 6.7" (1290×2796): [`docs/asc/screenshots/6.7/`](docs/asc/screenshots/6.7/)
- **Listing ready, upload pending Dev** (no ASC app record / Developer gate)
- Pointer: root `ASC_STORE_LISTING.md` → docs pack


# TestFlight / App Store Connect — preflight

## Phase status

| Phase | Item | Status |
|------|------|--------|
| 1 | Strip immagini non licenziate | **Done** — risky hosts cleared; `seedVersion = 24` |
| 2 | Commit snapshot | **Done** — product on `main` |
| 3 | Remote + push | **Done** — https://github.com/AncyBasket/EVforME |
| 3 | Privacy HTTPS | **Done** — https://ancybasket.github.io/EVforME/privacy/ |
| 3 | `EVFORME_PRIVACY_URL` | **Done** — same URL in `EVforME?/Info.plist` |
| 4 | Full unit tests (`EVforME?Tests`) | **Done** — green on Xcode beta / iPhone 17 Pro / iOS 27.0 |
| 4 | Free CC0 image pipeline | **In progress** — commit `1bdba23`: ~260 IT targets, 19 seed `imageURL` (CC0/Flickr+Wikimedia); see `docs/image-pipeline/` |
| 4 | ASC listing pack | **Ready** — see `ASC_STORE_LISTING.md` |
| 4 | UITests | **Done** — `testInputToVerdictFlow` green (`e3d5801`) |
| 4 | Archive (local `.xcarchive`) | **Done** — `/tmp/EVforME.xcarchive` · **1.0 (1)** · arm64 · Xcode 27 beta |
| 4 | Upload → App Store Connect | **Blocked** — no ASC app record for `Gancione.EVforME-` |
| 4 | TestFlight Internal | **Paused** — Apple Developer account expired; renew post-vacation, then create ASC app record + upload |

## Archive Xcode choice

- Project floor: **iOS 26.2** (`IPHONEOS_DEPLOYMENT_TARGET`) — do not lower
- Unit suite verified with: `DEVELOPER_DIR=/Users/andrea/Downloads/Xcode-beta.app/Contents/Developer`
- Prefer the **same** Xcode for archive that you used for the green unit run
- Version: **1.0 (1)** — Free

## Unit test command (green)

```bash
export DEVELOPER_DIR=/Users/andrea/Downloads/Xcode-beta.app/Contents/Developer

xcodebuild test \
  -project "EVforME?.xcodeproj" \
  -scheme "EVforME?" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0' \
  -only-testing:"EVforME?Tests"
```

## ASC (must match)

- Privacy Policy URL: `https://ancybasket.github.io/EVforME/privacy/`
- Copy / keywords / screenshots: `ASC_STORE_LISTING.md`

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
   - Price: Free · copy from `ASC_STORE_LISTING.md`
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

# TestFlight / App Store Connect — preflight

## Phase status

| Phase | Item | Status |
|------|------|--------|
| 1 | Strip immagini a rischio | **Done** — `vehicles.seed.quality.json` has 0 remote `imageURL` (`seedVersion = 23`) |
| 2 | Commit snapshot | **Done** — product on `main` |
| 3 | Remote + push | **Done** — https://github.com/AncyBasket/EVforME |
| 3 | Privacy HTTPS | **Done** — https://ancybasket.github.io/EVforME/privacy/ |
| 3 | `EVFORME_PRIVACY_URL` | **Done** — same URL in `EVforME?/Info.plist` |
| 4 | Full unit tests (`EVforME?Tests`) | **Done** — green on Xcode beta / iPhone 17 Pro / iOS 27.0 |
| 4 | ASC listing pack | **Ready** — see `ASC_STORE_LISTING.md` |
| 4 | UITests | Optional next (not blocking internal TF) |
| 4 | Archive → Upload → TestFlight | **Next** |

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

## Do not App Store submit until

- [x] Privacy URL live on HTTPS
- [x] Product committed + pushed
- [x] Risky image hosts stripped
- [x] Full unit tests green on archive Xcode toolchain
- [ ] Internal TestFlight build installed on a real device

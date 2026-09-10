# TestFlight / App Store Connect — preflight

## Status (repo)

| Blocker | Status |
|--------|--------|
| Privacy policy HTML | Ready: `docs/privacy/index.html` |
| `EVFORME_PRIVACY_URL` | **Needs live HTTPS URL** then paste into Info.plist + ASC |
| `.gitignore` | Added |
| Image license risk | Script: `scripts/strip_unlicensed_images.py` (strip Edidomus / Wikimedia / catbox images) |
| Catalog CDN catbox | Cleared for TF offline-first (`EVFORME_CATALOG_URL` empty) |
| Git commit of product | Do after strip + green tests |
| Git remote | Needs your GitHub/Cursor remote |
| Floor iOS 26.2 | Keep for now if building with Xcode 26/27 beta; lowering is a separate product decision |
| Full test suite | Run before archive |

## This week — ship checklist

1. **Host privacy**  
   Upload `docs/privacy/index.html` to any static HTTPS host (GitHub Pages, Netlify, your domain).  
   Example after Pages: `https://<user>.github.io/EVforME/privacy/`

2. **Wire URL**
   - Info.plist `EVFORME_PRIVACY_URL` = that URL  
   - App Store Connect → App Privacy / Privacy Policy URL = same URL

3. **Images for TF**
   ```bash
   python3 scripts/strip_unlicensed_images.py
   ```
   Bump `seedVersion` in `VehicleCatalogService` so devices drop old cached images.

4. **Git**
   ```bash
   git add -A && git commit  # product snapshot
   git remote add origin <your-repo>
   git push -u origin main
   ```

5. **Tests**
   ```bash
   DEVELOPER_DIR=… xcodebuild test -scheme "EVforME?" -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0'
   ```

6. **ASC package** (from `MARKETING_GTM.md`)
   - Subtitle: personalised EV vs ICE costs in minutes  
   - Keywords: auto elettrica, costi, TCO, ricarica, PHEV, Italia…  
   - Screenshots IT + EN  
   - Version `1.0` build `1`, price Free

## Do not submit until

- [ ] Privacy URL live on HTTPS  
- [ ] Product committed (and ideally pushed)  
- [ ] Risky image hosts stripped (or properly licensed)  
- [ ] Full unit tests green on the Xcode you archive with  

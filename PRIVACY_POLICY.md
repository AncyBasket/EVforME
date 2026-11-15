# Privacy Policy — EVforME?

**Last updated:** 20 October 2026  
**App:** EVforME? (iOS)

The canonical public privacy policy lives at:

**https://ancybasket.github.io/EVforME/privacy/**

That page (same date) is what App Store Connect and in-app “Open privacy policy” point to. This file is a short mirror for the repository.

## Summary (aligned with PrivacyInfo.xcprivacy)

- **Data Not Collected** in the app privacy manifest (`NSPrivacyCollectedDataTypes` empty; `NSPrivacyTracking` = false).
- Simulation inputs, history, and widget snapshots stay **on device** by default.
- **Location When In Use** only if you open Nearby chargers (Apple MapKit); not used for the country/cost market picker.
- Public energy price refresh (MIMIT fuel + Eurostat electricity) is used as **Italian official defaults only when the in-app market is Italy**. Outside Italy you enter your own prices; those Italian sources are not applied as silent defaults.
- Optional analytics / lead webhook URLs are empty in Release builds unless the developer configures them — nothing is sent when empty.

For full Italian/English text, rights, and contact details, use the public page above.

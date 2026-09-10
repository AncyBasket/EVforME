# Privacy Policy — EVforME?

**Last updated:** 9 September 2026  
**App:** EVforME? (iOS)

This policy describes how the EVforME? app handles information. It is written for App Store review and for people using the app in Italy and the EU.

## Who we are

EVforME? is a decision tool that estimates whether switching from a combustion car to an electric or plug-in hybrid car may make sense for your driving profile. It is provided by the app developer listed on the App Store product page (“we”, “us”).

## What the app does with data

### On your device (default)

Most processing stays on your iPhone:

- Driving and cost inputs you enter (km/year, fuel and electricity prices, charging preferences, selected vehicles)
- Simulation results and scenario history stored locally
- Optional lead form fields you type (name, email, city) until/unless you send them
- Widget / Live Activity snapshots shared only via the app’s App Group on the same device

We do **not** sell personal data. We do **not** use advertising trackers in the current build (`NSPrivacyTracking` = false).

### Photos

If you use sticker scanning, photos are used **on-device** to read consumption figures (L/100 km or kWh/100 km). Photos are not uploaded for that feature.

### Optional network features

When configured by the developer, the app may contact:

- A **vehicle catalog** HTTPS endpoint (public JSON) to refresh model data
- **Public energy price sources** (e.g. official fuel/electricity statistics)
- An optional **analytics** ingest URL (product events such as “verdict shown”)
- An optional **lead webhook** if you submit the advisor contact form with consent

If those URLs are empty (typical production default for analytics/leads), related data stays on device or is not sent.

## Data we may collect (App Privacy labels)

As declared in the app’s privacy manifest:

- **Name** and **email** — only if you fill the voluntary advisor form; purpose: app functionality / follow-up you request
- **Product interaction** — anonymous/local analytics events for improving the product (and optional remote ingest if configured)

## Legal bases (EU/UK GDPR style)

- **Contract / service delivery:** running the simulation you request
- **Consent:** advisor lead form and any optional remote analytics where consent is required
- **Legitimate interest:** securing the app, preventing abuse, and basic product metrics without advertising profiling

## Retention

- Local inputs and history remain until you delete the app or clear app data
- Lead/analytics payloads retained by any configured webhook/ingest follow that service’s retention; if none is configured, nothing is sent

## Your choices

- Do not fill the lead form if you do not want to share contact details
- Revoke photo access in iOS Settings → EVforME?
- Delete the app to remove local storage on device
- Contact us via the App Store support URL to request assistance with remotely stored leads (only if you previously submitted them to a configured webhook)

## Children

EVforME? is not directed at children under 13 (or the minimum age required in your country). Do not submit personal data about children through the lead form.

## International transfers

If you enable optional remote endpoints hosted outside your country, data you send may be processed in those regions under the provider’s terms.

## Changes

We may update this policy when the app’s data practices change. The “Last updated” date will change accordingly. Material changes that require consent will be surfaced in the app when feasible.

## Contact

Use the support contact shown on the App Store listing for EVforME?.

---

### Hosting note for App Store Connect

Paste this document on a public HTTPS page and set that URL as the Privacy Policy URL in App Store Connect. Optionally set `EVFORME_PRIVACY_URL` / Info.plist key to the same URL so the in-app screen can open it.

# EVforME? Go-To-Market Assets

## Landing Copy

- Headline: `In 3 minutes capisci se passare a EV conviene davvero.`
- Subheadline: `Confronto personalizzato su costi, ricarica e scenario reale: niente marketing, solo numeri.`
- Primary CTA: `Prova la simulazione`
- Secondary CTA: `Esporta report PDF (gratis)`

## Paid Ads Angles

- Angle A (risparmio): `Stai spendendo troppo per km? Scoprilo in 3 minuti.`
- Angle B (ricarica): `Ricarica EV: semplice o stress? Te lo diciamo sui tuoi dati.`

## Analytics Event Schema

- `onboarding_completed`
  - params: none
- `simulation_started`
  - params: `scenario`, `hasHomeCharging`, `ownershipYears`
- `verdict_shown`
  - params: `verdict`, `scenario`
- `report_requested`
  - params: `priceVariant`
- `lead_submitted`
  - params: `cityFilled`, `emailFilled`, `consent`

Implementation notes:
- Runtime tracker: `GrowthTracker.shared.track(...)`
- Local event log export: `GrowthTracker.shared.exportEventsJSON()`
- Quick funnel counters: `GrowthTracker.shared.funnelSnapshot()`

## Pricing Experiment

- Deferred: app stays free for now (PDF report unlocked for everyone).
- Legacy A/B variants (`4.99` / `9.99`) remain in code for a future monetization experiment only.

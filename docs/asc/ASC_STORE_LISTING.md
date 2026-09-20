# App Store Connect — listing pack (EVforME? 1.1–1.3)

**Status:** Listing ready for paste into ASC · **upload pending** (Developer / app record)  
**Product base:** `9ea6954` (+ smoke) · free · iOS 17+  
**Privacy (live):** https://ancybasket.github.io/EVforME/privacy/  
**Screenshots:** [`docs/asc/screenshots/6.7/`](screenshots/6.7/) · notes in [`screenshots/README.md`](screenshots/README.md)

Canonical pack for Connect. Root `ASC_STORE_LISTING.md` points here.

---

## Identity

| Field | Value |
|------|--------|
| Name (≤30) | `EVforME?` |
| Bundle ID | `Gancione.EVforME-` |
| Version to ship | `1.3` |
| Price | **Free** (no IAP) |
| Primary category | **Lifestyle** — decisione personale su auto / mobilità, non un tool B2B |
| Secondary category | **Utilities** — calcolatore on-device (costi, km, scenario) |
| Age rating | **4+** — no UGC, no chat, no unrestricted web; location optional for map only |
| Privacy Policy URL | https://ancybasket.github.io/EVforME/privacy/ |
| Support URL | **TODO Andrea** — interim: https://github.com/AncyBasket/EVforME/issues (no new domain). Optional later: GitHub Pages `/support/` under existing `ancybasket.github.io/EVforME/` |
| Marketing URL (optional) | https://github.com/AncyBasket/EVforME |

---

## Italian (primary storefront)

### Name
`EVforME?`

### Subtitle (≤30)
`Conviene passare all'EV?`  
*(24 characters)*

### Promotional text (optional, editable without full review)
`Verdetto personalizzato, ultimo confronto, bollo/incentivi orientativi e colonnine vicine — gratis, sul dispositivo.`

### Keywords (≤100, comma-separated, **no space after commas**)
`elettrica,EV,PHEV,costi,bollo,incentivi,colonnine,ricarica,TCO,Italia`  
*(69 characters)*

### Description
```
EVforME? ti aiuta a capire se passare da un’auto a combustione a un’elettrica o ibrida plug-in ha senso per i tuoi km e per come ricarichi.

Inserisci chilometri, prezzi e le due auto: ottieni un verdetto chiaro (sì / dipende / non ancora), risparmio stimato, ricariche settimanali e tempo di pareggio — calcolo sul dispositivo, senza account.

Cosa trovi nell’app
• Banco di prova con catalogo veicoli e scenari ottimistico / realistico / pessimistico
• Ultimo confronto: riapri, ricalcola con i dati di oggi o ripristina il form
• Kit Italia: finestra incentivo (“se compro entro…”), stime orientative di bollo, assicurazione e manutenzione (ICE vs EV)
• Colonnine vicine: mappa leggera via Mappe Apple (ricerca locale), posizione solo se la chiedi
• Guide brevi, report PDF gratis, widget / Live Activity sul verdetto

Gratis. Niente abbonamenti.

Trasparenza
Incentivi, bollo e costi di possesso sono stime semplificate per orientarti — non sono consulenza fiscale, legale, assicurativa o medica, né cifre ACI / compagnie ufficiali. Verifica sempre fonti ufficiali prima di decidere.
```

### What’s New (1.1–1.3)
```
1.3 Colonnine vicine — mappa MapKit, posizione solo on-demand, ricerca per città e Apri in Mappe.
1.2 Kit Italia — finestra incentivo, stime bollo / assicurazione / manutenzione con disclaimer.
1.1 Retention — card Ultimo confronto, ricalcolo con dati live, reminder locali soft.

Sempre gratis, calcolo on-device. Le stime non sono consulenza fiscale o legale.
```

---

## English (minimum)

### Subtitle (≤30)
`Is an EV right for you?`  
*(22 characters)*

### Promotional text (optional)
`Personal verdict, last comparison, indicative IT costs, and nearby chargers — free, on-device.`

### Keywords
`electric,EV,PHEV,cost,roadtax,incentives,chargers,TCO,Italy,compare`  
*(67 characters)*

### Short description (for quick paste / metadata notes)
`On-device EV vs ICE verdict for your km and charging. Last comparison, indicative Italian road-tax/incentive notes, nearby chargers via Apple Maps. Free — estimates, not tax advice.`

### Description (full, low effort)
```
EVforME? helps you decide whether switching from a combustion car to an EV or plug-in hybrid fits your yearly kilometres and charging setup.

Enter km, prices and two vehicles for a clear verdict (yes / maybe / not yet), estimated savings, weekly charges and break-even — computed on your iPhone, no account required.

What’s inside
• Workshop bench with vehicle catalog and optimistic / realistic / pessimistic scenarios
• Last comparison: reopen, recalculate with today’s data, or restore the form
• Italy kit: incentive window (“if I buy by…”), indicative road tax, insurance and maintenance (ICE vs EV)
• Nearby chargers: lightweight Apple Maps search; location only when you open the map
• Short guides, free PDF report, widget / Live Activity

Free. No subscriptions.

Transparency
Incentives, road tax and ownership costs are simplified estimates to orient you — not tax, legal, insurance or medical advice, and not official ACI or insurer quotes. Always check official sources before deciding.
```

### What’s New (EN)
```
1.3 Nearby chargers — MapKit map, on-demand location, city search, Open in Maps.
1.2 Italy kit — incentive window plus indicative road tax / insurance / maintenance with disclaimer.
1.1 Retention — last comparison card, live recalculation, soft local reminders.

Still free and on-device. Estimates are not tax or legal advice.
```

---

## Screenshot sequence (6.7")

Folder: `docs/asc/screenshots/6.7/` — all **1290 × 2796**.

| # | File | Story |
|---|------|--------|
| 1 | `01_verdict_aha.png` | Verdetto / aha |
| 2 | `02_ultimo_confronto.png` | Retention 1.1 |
| 3 | `03_kit_italia_costi.png` | Bollo / assic / manut. 1.2 |
| 4 | `04_workshop_input.png` | Workshop input |
| 5 | `05_colonnine_milano.png` | Colonnine 1.3 (Milano) |
| 6 | `06_guides_hub.png` | Guides + entry colonnine (opz.) |
| 7 | `07_guides_bollo.png` | Scheda bollo (opz.) |
| 8 | `08_colonnine_sheet.png` | Map sheet (opz.) |

Upload **1–5** as minimum; add 6–8 if Connect allows more. For **6.1"** reuse the same files first (see `screenshots/README.md`). Raw smoke sources remain in `docs/smoke/shots/` (1206 × 2622).

No heavy marketing mockups; Simulator UI only (light pad bars from resize).

---

## App Privacy / Review notes (for ASC reviewer)

Paste into **Notes for Review** (adapt as needed):

```
EVforME? is a free decision-support app (no IAP, no account).

• Simulation and history stay on-device by default.
• Optional network: public energy prices / catalog refresh / Apple MapKit search — no EVforME backend for location.
• Location: When In Use only, requested when the user opens Nearby chargers; deny still allows city search or Open in Maps. No background location.
• Italian incentives, road tax, insurance and maintenance figures are simplified estimates with in-app disclaimers — not tax, legal or insurance advice.
• Notifications (optional): soft local reminders after a saved verdict; user can deny.
• Test: open workshop → simulate → verdict; Guides → Colonnine vicino a te → city “Milano”.
```

### Privacy nutrition (aligned with PrivacyInfo + policy)

- Data not sold; no advertising tracking (`NSPrivacyTracking` = false)
- Precise location: App Functionality only, if user allows for the map
- Name/email: only if user submits optional advisor form

---

## Paste checklist

- [ ] Name + subtitle IT / EN  
- [ ] Keywords IT / EN  
- [ ] Description + What’s New  
- [ ] Privacy URL + Support URL (confirm Issues or Pages with Andrea)  
- [ ] Categories Lifestyle + Utilities  
- [ ] Age 4+ / no UGC  
- [ ] Screenshots 6.7" in order  
- [ ] Review notes  
- [ ] **Upload build** — blocked until Developer / ASC app record  

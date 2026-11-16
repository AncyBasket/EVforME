# App Store Connect — listing pack (EVforME? 1.4)

**Status:** Listing ready for paste into ASC  
**Product base:** main @ `c7fa700` (seed 88) · free · iOS 17+  
**Privacy (live):** https://ancybasket.github.io/EVforME/privacy/  
**Screenshots:** [`docs/asc/screenshots/6.7/`](screenshots/6.7/) · notes in [`screenshots/README.md`](screenshots/README.md)

Canonical pack for Connect. Root `ASC_STORE_LISTING.md` points here.

---

## Identity

| Field | Value |
|------|--------|
| Name (≤30) | `EVforME?` |
| Bundle ID | `Gancione.EVforME-` |
| Version to ship | `1.4` |
| Price | **Free** (no IAP) |
| Primary category | **Lifestyle** — decisione personale su auto / mobilità, non un tool B2B |
| Secondary category | **Utilities** — calcolatore on-device (costi, km, scenario) |
| Age rating | **4+** — no UGC, no chat, no unrestricted web; location optional for map only |
| Privacy Policy URL | https://ancybasket.github.io/EVforME/privacy/ |
| Support URL | https://ancybasket.github.io/EVforME/support/ |
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
• Kit Italia: stato Bonus MASE (chiuso 2025), stime orientative di bollo, assicurazione e manutenzione (ICE vs EV)
• Fuori Italia: inserisci i tuoi prezzi — niente default MIMIT/Eurostat/Adiconsum/IVASS
• Colonnine vicine: mappa leggera via Mappe Apple (ricerca locale), posizione solo se la chiedi
• Guide brevi, report PDF gratis, widget / Live Activity sul verdetto

Gratis. Niente abbonamenti.

Trasparenza
Incentivi, bollo e costi di possesso sono stime semplificate per orientarti — non sono consulenza fiscale, legale, assicurativa o medica, né cifre ACI / compagnie ufficiali. Verifica sempre fonti ufficiali prima di decidere.
```

### What’s New (1.4)
```
1.4 Mercato onesto — fuori Italia niente prezzi italiani precompilati; inserisci i tuoi. Catalogo US/EPA solo per US/CA. Privacy e listing allineati (Data Not Collected).
1.3 Colonnine vicine — mappa MapKit, posizione solo on-demand, ricerca per città e Apri in Mappe.
1.2 Kit Italia — finestra incentivo, stime bollo / assicurazione / manutenzione con disclaimer.

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

### Description (full)
```
EVforME? helps you decide whether switching from a combustion car to an EV or plug-in hybrid fits your yearly kilometres and charging setup.

Enter km, prices and two vehicles for a clear verdict (yes / maybe / not yet), estimated savings, weekly charges and break-even — computed on your iPhone, no account required.

What’s inside
• Workshop bench with vehicle catalog and optimistic / realistic / pessimistic scenarios
• Last comparison: reopen, recalculate with today’s data, or restore the form
• Italy kit: Bonus MASE status (closed 2025), indicative road tax, insurance and maintenance (ICE vs EV)
• Outside Italy: enter your own prices — no silent Italian MIMIT/Eurostat/Adiconsum/IVASS defaults
• Nearby chargers: lightweight Apple Maps search; location only when you open the map
• Short guides, free PDF report, widget / Live Activity

Free. No subscriptions.

Transparency
Incentives, road tax and ownership costs are simplified estimates to orient you — not tax, legal, insurance or medical advice, and not official ACI or insurer quotes. Always check official sources before deciding.
```

### What’s New (EN)
```
1.4 Honest markets — outside Italy no pre-filled Italian prices; enter yours. US/EPA catalog rows only for US/CA. Privacy + listing aligned (Data Not Collected).
1.3 Nearby chargers — MapKit map, on-demand location, city search, Open in Maps.
1.2 Italy kit — incentive window plus indicative road tax / insurance / maintenance with disclaimer.

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

Upload **1–5** as minimum; add 6–8 if Connect allows more.

---

## App Privacy / Review notes (for ASC reviewer)

```
EVforME? is a free decision-support app (no IAP, no account).

• Simulation and history stay on-device by default.
• Optional network: public energy prices (Italy market only) / catalog refresh / Apple MapKit search — no EVforME backend for location.
• Location: When In Use only, requested when the user opens Nearby chargers; deny still allows city search or Open in Maps. No background location.
• Italian incentives, road tax, insurance and maintenance figures are simplified estimates with in-app disclaimers — not tax, legal or insurance advice.
• Outside Italy the app does not pre-fill Italian MIMIT/Eurostat/Adiconsum/IVASS defaults; the verdict waits for user prices.
• Notifications (optional): soft local reminders after a saved verdict; user can deny.
• Test: open workshop → simulate → verdict; Guides → Colonnine vicino a te → city “Milano”.
```

### Privacy nutrition (aligned with PrivacyInfo + policy)

- **Data Not Collected** — `NSPrivacyCollectedDataTypes` empty; `NSPrivacyTracking` = false
- Release: analytics ingest URL and lead webhook are empty unless developer-configured (verified in `Defaults.swift` `#else` branches)
- ASC App Privacy answers: **Data Not Collected** (no Name / Email / Precise Location collected by EVforME for App Privacy labels)

---

## Paste checklist

- [ ] Name + subtitle IT / EN  
- [ ] Keywords IT / EN  
- [ ] Description + What’s New 1.4  
- [ ] Privacy URL + Support URL  
- [ ] Categories Lifestyle + Utilities  
- [ ] Age 4+ / no UGC  
- [ ] Screenshots 6.7" in order  
- [ ] Review notes  
- [ ] App Privacy: Data Not Collected  

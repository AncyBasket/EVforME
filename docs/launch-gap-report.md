# Launch gap report — EVforME?

**Branch:** `audit/launch-gap`  
**Data verifica:** 2026-10-27  
**Scope:** solo audit (nessuna modifica a codice/seed). App al lancio **gratis**. Catalogo **completo** (non si tolgono auto).  
**Commit base:** `main` @ `fe6c838` (seed v62).

Allegato: [`docs/launch-gap-coverage.csv`](launch-gap-coverage.csv) — tutti i 5627 parent modello/anno, ordinati per immatricolazioni EEA IT brand+model sommate 2022–2025.

---

## 1) Copertura di tutto il catalogo

**Stato: parziale**

### Cosa c’è oggi (verificato)

| Voce | File / evidenza |
|------|-----------------|
| Seed bundlato | `EVforME?/Data/vehicles.seed.quality.json` — **6750** righe = **5627** parent + **1123** versioni figlie (`parentId`) |
| Seed version | `EVforME?/Data/catalog_cdn.json` → `seedVersion: 62` |
| Campi seed presenti | `batteryKWh`, `brand`, `model`, `year`, `powertrain`, `fuelKind`, `energyConsumptionKWhPerKm`, `fuelConsumptionLPerKm`, `wltpRangeKm`, `wltpConsumptionKWh100km`, `sourceName`, `sourceUpdatedAt`, `taxesPerYear`, `maintenancePerYear`, `officialMatched`, `trim`, … |
| Campi **assenti** nel seed | Nessun `listPriceEUR` / `msrp` / `priceEUR` (verificato sull’unione delle chiavi JSON) |
| EEA IT cache | `scripts/cache/eea/IT_*.json` — **174** file; aggregazione `models → years → …`, `doc_count`; `_fetched_at` tipico 2026-10-24/25 |

### Conteggi parent per alimentazione (seed, no ipotesi)

| Alimentazione | Modelli (parent) | Con versioni figlie | `officialMatched` (almeno 1) | Trim nominato (non solo «Versione n») | Batteria | Autonomia WLTP | Consumo | Prezzo listino | `sourceName` |
|---------------|------------------|---------------------|------------------------------|----------------------------------------|----------|----------------|---------|----------------|--------------|
| BEV | 701 | 399 | **18** | 22 | 17 | 442 | 701 | **0** | 701 |
| PHEV | 10 | 0 | 0 | 10 | **0** | 10 | 10 | **0** | 10 |
| ibrida (HEV) | 122 | 0 | 0 | 30 | 0 | 0 | 122 | **0** | 122 |
| benzina | 3534 | 0 | 0 | 5 | 0 | 0 | 3534 | **0** | 3534 |
| diesel | 1076 | 0 | 0 | 0 | 0 | 0 | 1076 | **0** | 1076 |
| GPL | 129 | 0 | 0 | 6 | 0 | 0 | 129 | **0** | 129 |
| metano | 55 | 0 | 0 | 0 | 0 | 0 | 55 | **0** | 55 |
| **Totale** | **5627** | **399** | **18** | — | — | — | **5627** | **0** | **5627** |

Note verificate:

- Versioni figlie solo su BEV (pipeline EV variants). Figli con `officialMatched: true`: **34** (su 1123).
- Batteria: quasi assente; PHEV **0/10** con `batteryKWh` anche quando `sourceName` cita kWh (es. `bmw-330e-phev-2024`).
- Consumo: presente su tutti i parent (elettrico e/o L/km).
- Fonte: ogni parent ha `sourceName`; qualità eterogenea (`seed+EEA-WLTP`, `stima (…)`, listini IT puntuali, ecc.).
- Prezzo di listino: **manca nel catalogo**; in app il prezzo acquisto è input utente o `Defaults.suggestedPurchasePrice` (`EVforME?/Core/Constants/Defaults.swift` L26–38).

### CSV immatricolazioni IT

- File: `docs/launch-gap-coverage.csv`.
- Fonte conteggi: `doc_count` su `years` nei file `IT_*` (Paese `MS=IT` nella query), anni **2022–2025**.
- Grano: **modello commerciale EEA × anno** (carburanti sommati a livello model/year). Stesso totale può ripetersi su varianti catalogo benzina/GPL/metano dello stesso modello.
- Match catalogo↔EEA: brand+model normalizzati, soft substring; **non** 1:1 sulle omologazioni tipo `118D` ↔ «Serie 1».
- Ordinamento: `it_regs_brand_model_sum_2022_2025` desc, poi anno del parent.

### Modelli venduti in IT (≥500 immatricolazioni/anno) assenti dal catalogo

**Stato: manca (lista parziale ma verificata)**

Metodo: EEA IT `doc_count` ≥ 500 per anno 2022–2025; esclusi i casi già presenti dopo alias (es. `DS7`↔`DS 7`, `TUCSONIX35`↔`Tucson`, `ID3`↔`ID.3`). Restano **212** righe anno×modello / **98** famiglie modello.

Esempi ad alto volume (max `doc_count` annuale osservato):

| Max regs/anno | Brand | Modello EEA | Anni ≥500 | Note catalogo |
|---------------|-------|-------------|-----------|---------------|
| 42556 | TOYOTA | AYGO X | 2023–2025 | C’è solo `toyota-aygo-petrol-2022` (Aygo, non Aygo X) |
| 18318 | FORD | ECOSPORT | 2022–2023 | 0 hit catalogo |
| 14002 | ALFA ROMEO | JUNIOR | 2024–2025 | 0 hit |
| 11186 | MINI | COOPER | 2022–2024 | In catalogo Clubman/Convertible/Countryman, non Cooper hatch |
| 8448 | BMW | 118D | 2022–2025 | Nessuna «Serie 1» / codice 118 in catalogo 2022–2025 |
| 6647 | RENAULT | SYMBIOZ | 2024–2025 | 0 hit |
| 5458 | LEXUS | LBX | 2024–2025 | 0 hit |
| 3906 | DACIA | BIGSTER | 2025 | 0 hit |
| 3596 | MASERATI | GRECALE GT | 2022–2025 | 0 hit |
| 3176 | HONDA | ZR V | 2023–2025 | 0 hit |
| 2682 | VOLKSWAGEN | CADDY | 2022–2025 | 0 hit |
| 2405 | CUPRA | TERRAMAR | 2024–2025 | 0 hit |
| 8126 | SMART | FORTWO | 2022 | Fortwo in catalogo solo 2023–2025 |

Lista completa anno×modello usata per il conteggio: generata in audit da `scripts/cache/eea/IT_*.json` (non inventata). Alcuni “buchi” BMW/Mercedes sono **codici omologazione** vs naming marketing: vanno trattati a parte (mapping, non solo insert).

**PR stimate per §1:** 4–5 (scaglioni vendite + mapping omologazione + listino + batterie PHEV/BEV).

---

## 2) Costi e fonti

**Stato: parziale** (fonti forti su energia; stime fisse su bollo/RC/manutenzione/svalutazione; listino assente)

| Valore usato nei calcoli | Dove | Data / periodo | Aggiornamento | Mostra fonte/data in UI? |
|--------------------------|------|----------------|---------------|---------------------------|
| Benzina / gasolio / GPL / metano | Bundle `EVforME?/Data/official_energy_costs.json` + fetch MIMIT (`Defaults.mimitFuelPricesCSVURL`, `OfficialCostService`) | Bundle `updatedAt` **2026-10-19**; extraction MIMIT stessa data nel JSON `sources.fuel` | A ogni apertura (cache giornaliera MIMIT); offline → bundle/cache | Sì in parte: trust strip / note prezzi (`verdict_trust_strip`, `source_prices_note`, `prices_fresh_just_now` in `it.lproj/Localizable.strings`); **non** sempre la data MIMIT del giorno sul verdetto |
| Elettricità casa | Stesso JSON + Eurostat `nrg_pc_204` | Periodo **2026-S1** (`electricityPeriod`) | Fetch Eurostat a apertura; fallback bundle | Sì: `InputView` può mostrare `electricity_eurostat_period` se c’è periodo in cache (`InputView.swift` ~L358) |
| Colonnine pubbliche (€/kWh) | Costanti `PublicChargingPriceDefaults` in `ChargingCost.swift` L14–28 | Commento **Adiconsum settembre 2026** | **Fisso in codice** (override utente) | Sì: `public_charging_source_note` = «Adiconsum settembre 2026» |
| Bollo per regione | `ItalianRegion.swift` + `OwnershipCostEstimates.bollo*` in `EVSimulator.swift` L140–253 | Commenti tariffario **ACI/regioni 2026**; nazionale EV ripiego **2,58 €/kW** | Fisso in codice | Parziale: Kit Italia / assunzioni bollo; disclaimer stime |
| Incentivi | `EVforME?/Data/italian_incentives.json` | `updatedAt` 2026-10-19; `validUntil` **2026-06-30**; nota MASE chiuso | Bundle + eventuale remote `EVFORME_INCENTIVES_URL` | Sì: schedule/disclaimer; **non entra nel verdetto** se scaduto / toggle off (`sourceNote` nel JSON) |
| Assicurazione RC | `OwnershipCostEstimates.ivassAverageRCEURPerYear = 422` (`EVSimulator.swift` L114–115) | Commento «media IVASS 2° trim. **2026**» | Fisso (+ override / kasko utente) | Sì in reason `insurance_included_reason` (IVASS); **senza data trimestre in UI** |
| Manutenzione | `MarketMaintenanceRates` in `AppMarket.swift` L77–137 + `OperatingCostCalculator.maintenancePerYear` | Note Quattroruote 2022 / SicurAUTO 2023 (IT), Tec Alliance 2023 (DE), ecc. | Fisso per cluster mercato | Sì: `assumptionMaintenance(for:)` cita `sourceNote` del cluster |
| Svalutazione / residuo | `OwnershipCostEstimates.residualValue` (`EVSimulator.swift` L255–284) | Curve % annuali in codice (EV 18/14/12%, ICE 12/10%) | Fisso | Parziale: riga TCO residuo + `tco_residual_note`; non una fonte esterna datata |
| Prezzo listino veicolo | Non in seed; `Defaults.suggestedPurchasePrice` o input | Formula età×powertrain | Fisso / utente | No listino OEM |

Pagamenti / IAP: **fuori scope** (app gratis).

**PR stimate per §2:** 2 (listino+trasparenza date; eventuale refresh Adiconsum/IVASS con data in UI).

---

## 3) Verdetto e spiegazione

**Stato: OK con gap minori**

### Testi utente (verificati nel codice)

| Area | Contenuto | File |
|------|-----------|------|
| Headline verdetto | sì / dipende / non ancora | `VerdictEngine` + `VerdictView` |
| Sottotitolo opex | `verdictOpexOnlyUnderHeadline` | `VerdictView.swift` ~L465 |
| Proof strip | risparmio €/anno (banda), ricariche/sett., **mesi di pareggio** | L495–512; `breakEvenMonths` da `EVSimulator` L598–608 |
| Trust strip | «Calcolo sul dispositivo · Carburante MIMIT ed elettricità Eurostat; altre voci stimate» | `verdict_trust_strip` |
| Key reasons | switch auto, charge/week, save/current cheaper, home/public charging, PHEV blend, RC IVASS, intent, sticker, opex/pareggio | `EVSimulator` L623–663 |
| Fear / reality | frasi fisse su batteria, ricarica, affidabilità, costi | L665–687 — **non** tutte legate a un numero misurato (es. «fewer parts») |
| Assunzioni | consumi effettivi, prezzi fuel/elec, manutenzione cluster, taxes, disclaimer IT | `VerdictAssumptions` + `VerdictView` L635+ |
| Kit Italia | bollo / RC / manutenzione ICE vs EV | `VerdictView` L686+ |
| TCO extra | residui stimati | L745–761 |
| How we calculate | spiegone dedicato | `HowWeCalculateExplainer` / view |

### Pareggio

- **Sì**, in mesi: `breakEvenMonths = ceil(purchasePremium / yearlySavings * 12)` se intent = acquisto e savings > 50 €/anno (`EVSimulator.swift` L598–608).
- Mostrato in proof + reason + badge storico.
- Conversione in **anni e km**: mesi sì; km di pareggio **non** come campo dedicato (derivabile da mesi × km/anno utente, non esposto come metrica primaria).

### Condivisione

- **Sì:** `ShareLink` card + export PDF (`VerdictView` L365–396, `FreeReportSheet`, `PDFReportService`).

### Frasi senza numero di supporto

- Fear/reality generiche (`fearEvsUnreliable` / `realityFewerParts`).
- Alcune reason qualitative (`homeChargingEasier`, `publicChargingManageable`).
- Stima residuo senza fonte esterna.

**PR stimate per §3:** 1 (affinare copy fear/reality + eventuale pareggio in km).

---

## 4) Qualità

**Stato: OK / parziale**

| Check | Stato | Evidenza |
|-------|-------|----------|
| Tempo avvio simulatore | OK | `testLaunchPerformance` → **average AppLaunch 0.852 s** (log 2026-10-27) |
| Offline | OK | Catalogo seed bundlato; `VehicleCatalogService` offline-first; prezzi da bundle se rete assente (`OfficialCostService.cachedOrBundledCosts`) |
| Testi EN rimasti (locale IT) | Parziale | UI prod via `L10n` + `it.lproj`; hardcode EN solo in debug `GrowthDebugView.swift` («Growth Funnel Snapshot») e brand `EVforME?` su share card |
| VoiceOver | Parziale | `accessibilityLabel` / `Hint` su verdetto, share, mappe, errori; **nessun test unit dedicato VoiceOver** |
| Dynamic Type | OK (smoke) | `SmokeProductUITests.testSmokeDynamicTypeXXXL_HomeAndAssumptions` **passed** |
| Warning build | OK | 1 warning tooling: AppIntents metadata skipped (no framework dependency) — non errore app |

**PR stimate per §4:** 0–1 (audit a11y più ampio se si vuole chiudere VoiceOver).

---

## 5) App Store

**Stato: parziale (pack pronto, upload pending)**

| Elemento | Stato | Dove |
|----------|-------|------|
| Icona | OK | `AppIcon.appiconset` — 1024 universal + dark + tinted |
| Privacy policy | OK contenuto; data **2026-10-08** in `PRIVACY_POLICY.md`; URL live citato in ASC | `docs/asc/ASC_STORE_LISTING.md`, https://ancybasket.github.io/EVforME/privacy/ |
| Localizzazione listing | OK IT + EN minimo | `docs/asc/ASC_STORE_LISTING.md` |
| Testi scheda | OK (name, subtitle, keywords, description, What’s New 1.1–1.3) | stesso |
| Screenshot 6.7" | OK set di 8 PNG | `docs/asc/screenshots/6.7/` |
| Screenshot 6.1" dedicati | Parziale | README: riusare 6.7 o riesportare se ASC li chiede |
| Prezzo | OK Free | ASC pack |
| Support URL | OK in pack canonico (root `ASC_STORE_LISTING.md` aveva ancora TODO — canonico in `docs/asc/` è aggiornato) | |
| Upload ASC / record app | **Manca** | Status doc: «upload pending» |

**PR stimate per §5:** 1 (ops: upload ASC + eventuale 6.1"), non codice.

---

## 6) Test

**Stato: OK**

- `pgrep -fl xcodebuild` prima della run: nessun build concorrente.
- Destinazione unica: Simulator `EVforME iPhone 16 Pro 18.6` (`DD9120E8-599A-401F-8ADE-AAA28507060D`).
- Flag: `-parallel-testing-enabled NO -maximum-concurrent-test-simulator-destinations 1`.
- Risultato: **`** TEST SUCCEEDED **`**

| Target | Conteggio esatto | Fallimenti | Saltati |
|--------|------------------|------------|---------|
| Unit (`EVforME?Tests.xctest`) | **279** | 0 | 0 |
| Swift Testing | **1** (`EVforME_Tests.example`) | 0 | 0 |
| UI (`EVforME?UITests.xctest`) | **18** (7 + 8 launch + 3 smoke) | 0 | 0 |

Log: `/tmp/evforme_launch_gap_tests.log`.

---

## Sintesi gap vs lancio gratis

| Area | Gap principale |
|------|----------------|
| Catalogo | Completo in ampiezza (5627 parent) ma **qualità versioni/nomi/batteria/listino** molto bassa fuori da 18 BEV abbinati OEM |
| Vendite IT | Decine di modelli ≥500 regs/anno assenti (Aygo X, Junior, Symbioz, LBX, Bigster, Grecale, Cooper, …) |
| Costi | Energia OK; possesso/stime OK con disclaimer; **nessun listino OEM** |
| Store | Pack pronto, **upload** ancora da fare |

---

## PR necessarie per il lancio (max 10)

Ordine consigliato; i lavori dati sono a **scaglioni per vendite IT** (prima ≥500/anno, poi resto catalogo). Nessuna PR di rimozione auto. Nessuna PR pagamenti.

| # | Titolo | Contenuto | Dipendenze |
|---|--------|-----------|------------|
| 1 | **Catalogo IT wave-1 (≥5k regs/anno mancanti)** | Inserire/allineare Aygo X, Alfa Junior, Mini Cooper (hatch), EcoSport, Symbioz, LBX, Fortwo 2022, … con consumo EEA IT + `sourceName`/`sourceUpdatedAt` | nessuna |
| 2 | **Catalogo IT wave-2 (0,5k–5k) + family BMW/Mercedes mapping** | Bigster, Grecale, Terramar, Caddy, Trafic, Kangoo, ZR-V, X4/X6/codici 1xx→Serie; tabella alias omologazione↔marketing senza inventare kW | dopo o parallela a 1 se file seed isolati |
| 3 | **BEV versioni: nomi ufficiali + batteria (top venduti IT)** | Continuare abbinamento OEM/archivio same-MY (Tesla/Kia/Volvo/VW/BMW demoted) senza inventare; ripristinare UI picker su Model Y abbinata | indipendente da 1–2; non toccare M3 2026 |
| 4 | **PHEV + BEV batteryKWh da fonte** | Dove la fonte già cita kWh (es. press BMW 330e) popolare il campo; 0 inventati | può seguire 3 |
| 5 | **Listino prezzi UE/IT per top venduti** | Campo listino + fonte/data; usare in suggest prezzo solo se presente | dopo wave-1 (stessi modelli) |
| 6 | **Trasparenza costi: date in UI** | Mostrare sempre data MIMIT / periodo Eurostat / Adiconsum / IVASS trimestre sulle assunzioni | nessuna |
| 7 | **Catalogo resto (scaglione 3)** | Coprire gap EEA IT rimanenti e buchi di naming fino a copertura completa del set immatricolato 2022–2025 | dopo 1–2 |
| 8 | **Copy verdetto: fear/reality + pareggio km** | Legare frasi a numeri o riformulare; opzionale km di pareggio | nessuna |
| 9 | **ASC upload + screenshot 6.1 se richiesto** | Incollare pack `docs/asc/`, caricare icona/screenshot, privacy/support URL | nessuna codice |
| 10 | **A11y pass VoiceOver schermate principali** | Audit VoiceOver su Workshop / Verdetto / Map / Guide + test smoke | dopo stabilità UI 1.3 |

**Fuori lista (voluto):** feature review-safety, bump versione non richiesti da questo audit; pagamenti.

# EVforME? Data Sources Playbook

Questo file contiene solo quello che serve per portare il catalogo a livello mercato:
- quali fonti usare
- quali campi estrarre
- quale fonte vince in caso di conflitto
- come aggiornare automaticamente

## Free path (attuale, senza provider a pagamento)

Finché l’app resta free senza Car2DB/EVOX:
1. Parti da seed + arricchimento EEA/WLTP (`scripts/enrich_consumption_from_eea.py`)
2. Genera campi qualità derivati con `scripts/enrich_catalog_quality_fields.py`
   → `EVforME?/Data/vehicles.seed.quality.json` (+ export `api/static/vehicles.catalog.json`)
3. L’app preferisce `vehicles.seed.quality` in bundle; in Debug può fare refresh da `GET /catalog/export`
4. I campi `confidenceScore` / `sourceName` / `batteryKWh` / `wltp*` sono **derivati** (non scheda ufficiale a pagamento)

## 1) Target data model (quello che serve all'app)

Campi necessari per `VehicleCatalogItem`:
- `id`
- `brand`
- `model`
- `year`
- `powertrain` (`ice` / `ev` / `phev`)
- `lengthM`
- `widthM`
- `heightM`
- `fuelConsumptionLPerKm`
- `energyConsumptionKWhPerKm`
- `maintenancePerYear`
- `taxesPerYear`
- `imageURL`

Campi extra consigliati (nuova versione):
- `trim`
- `batteryKWh`
- `wltpRangeKm`
- `wltpConsumptionKWh100km`
- `co2gKm`
- `market` (`IT`, `EU`)
- `sourceName`
- `sourceUpdatedAt`
- `confidenceScore`

## 2) Provider shortlist (pragmatico)

### A. Core catalog specs (obbligatorio)
- **Car2DB API** oppure **Auto-Data API**
- Uso: base completa make/model/year/trim + dimensioni + consumi
- Motivo: copertura ampia e aggiornamenti frequenti

### B. EV-specific enrichment (fortemente consigliato)
- **EV Database Data Services**
- Uso: EV range, consumi, prezzi mercato EV, archivio modelli dismessi
- Motivo: qualità EV molto alta

### C. Official WLTP/CO2 validation (compliance-grade)
- **EEA CO2 passenger cars dataset**
- **VCA UK fuel/emissions dataset**
- (enterprise) **CAP-HPI WLTP API**
- Uso: validazione ufficiale CO2/consumi omologati

### D. Images licensed (obbligatorio per produzione)
- **EVOX Images** / **VehicleImagery** / **Fuel API**
- Uso: immagini coerenti, licenza commerciale chiara

### E. Normalization fallback (gratuito)
- **NHTSA vPIC API**
- Uso: normalizzare make/model/year e dedup

## 3) Field mapping pratico (priorità fonti)

Ordine priorità per ogni campo:

- `brand`, `model`, `year`, `trim`
  1) Core catalog (Car2DB/Auto-Data)
  2) vPIC fallback

- `powertrain`
  1) Core catalog
  2) EVDB (se EV)

- `lengthM`, `widthM`, `heightM`
  1) Core catalog
  2) VCA/EEA cross-check

- `fuelConsumptionLPerKm` (ICE)
  1) Core catalog
  2) VCA/EEA

- `energyConsumptionKWhPerKm` (EV)
  1) EVDB
  2) Core catalog
  3) VCA/EEA

- `imageURL`
  1) Licensed image API
  2) `nil` (mai fonte non licenziata in produzione)

- `maintenancePerYear`, `taxesPerYear`
  1) Regole locali interne (non da provider globale)
  2) Tabelle paese/versione app

## 4) Regole di conflitto (da applicare sempre)

- Se due fonti differiscono su dimensioni/consumi:
  - tieni valore della fonte con priorità più alta
  - salva anche `sourceName` e `confidenceScore`
- Scarta record se mancano insieme:
  - `brand`, `model`, `year`, `powertrain`
- Per EV senza consumo:
  - fallback da `wltpConsumptionKWh100km / 100`
- Per ICE senza consumo:
  - fallback da WLTP mixed l/100 km -> `/100`

## 5) Pipeline auto-update (quella che ti serve davvero)

Job giornaliero (o settimanale):
1. Pull da Core catalog
2. Merge EVDB (solo EV)
3. Validate con EEA/VCA (where available)
4. Resolve conflitti (regole sopra)
5. Enrich immagini da provider licenziato
6. Export `vehicles.catalog.json` versioneata
7. Upload su endpoint remoto
8. App chiama `refreshFromRemoteIfPossible()`

## 6) Checklist minima "market-ready"

- [ ] Contratto/licenza provider dati firmato
- [ ] Contratto/licenza immagini firmato
- [ ] Copertura EU >= 90% segmenti target
- [ ] Update job automatico attivo
- [ ] QA automatico (campi nulli, outlier, duplicati)
- [ ] Versioning catalogo e rollback

## 7) Cosa usare subito (senza perdere tempo)

Fase 1 (rapida):
- Core: Car2DB o Auto-Data
- EV: EVDB
- Images: VehicleImagery o EVOX

Fase 2 (accuratezza):
- Aggiungi EEA/VCA cross-check

Fase 3 (enterprise):
- Aggiungi CAP-HPI WLTP

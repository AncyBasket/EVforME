# EVforME Internal Vehicle API

API opzionale (Debug / analytics / lead). **Il confronto in produzione non dipende da questa API.**

## Dati live usati dall’app (internet pubblico)

| Dato | Fonte | Quando |
|------|--------|--------|
| Benzina IT | MIMIT `prezzo_alle_8.csv` | ogni open / foreground |
| Elettricità IT | Eurostat `nrg_pc_204` | ogni open / foreground |
| Catalogo veicoli | CDN pubblico | ogni open / foreground |

## Aggiornare catalogo + foto (automatico)

Un solo comando — **non serve copiare URL**:

```bash
python3 scripts/update_live_catalog.py --skip-enrich   # solo ripubblica JSON
# oppure, se mancano foto / mappa Wikipedia:
python3 scripts/update_live_catalog.py
```

Lo script:
1. (opz.) arricchisce le immagini
2. carica il JSON sul CDN
3. aggiorna da solo `EVforME?/Data/catalog_cdn.json`, `Defaults.swift`, `Info.plist`

## Avvio API locale (opzionale)

```bash
cd api
python3 -m pip install -r requirements.txt
uvicorn main:app --reload --port 8787
```

Override locale: `EVFORME_CATALOG_URL=http://127.0.0.1:8787/catalog/export`

## Endpoint

- `GET /health`
- `GET /catalog/export` — JSON app-native
- `GET /static/vehicles.catalog.json`
- `POST /events` · `POST /leads`
- `GET /energy/default-costs`

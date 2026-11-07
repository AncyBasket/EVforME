# EVforME Internal Vehicle API

API opzionale per debug, analytics e richieste di consulenza. Il confronto in produzione resta offline-first e non dipende da questa API.

## Dati usati dall’app

| Dato | Fonte | Aggiornamento |
|------|--------|---------------|
| Carburante IT | MIMIT `prezzo_alle_8.csv` | all’apertura / ritorno in foreground |
| Elettricità IT | Eurostat `nrg_pc_204` | all’apertura / ritorno in foreground |
| Catalogo | seed incluso nell’app o CDN HTTPS configurata | all’apertura / ritorno in foreground |

Il mirror SQLite locale viene riallineato all’avvio quando `seedVersion` o il numero di righe nel manifest cambia.
`GET /catalog/export` include `confidencePolicyVersion`, `confidenceEvidence` e `confidenceScoreLegacy` oltre allo score corrente.

## Avvio locale

```bash
cd api
python3 -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8787 --reload
```

Per consultare lead/eventi o avviare una sincronizzazione amministrativa, configura un token casuale di almeno 32 caratteri:

```bash
export EVFORME_ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export EVFORME_RETENTION_DAYS=180  # default 180; intervallo supportato: 1–3650
uvicorn main:app --host 127.0.0.1 --port 8787 --reload
```

Esempio lettura protetta:

```bash
curl -H "Authorization: Bearer $EVFORME_ADMIN_TOKEN" http://127.0.0.1:8787/leads
```

Senza token admin valido, `GET /leads`, `GET /events`, `POST /catalog/sync` e `POST /energy/sync` restano disabilitati. I lead richiedono email valida e `consent: true`; vengono ripuliti e limitati. Gli analytics accettano solo valori scalari brevi e rifiutano campi personali comuni. Gli invii pubblici sono limitati a 5 lead/minuto e 120 eventi/minuto per IP nel singolo processo; il corpo massimo è 16 KiB. Lead ed eventi vengono eliminati oltre la retention configurata (180 giorni di default).

## Endpoint

- `GET /health`
- `GET /catalog/state`
- `GET /catalog/export` e `GET /static/vehicles.catalog.json`
- `GET /energy/default-costs`
- `POST /events` e `POST /leads` (ingestione pubblica limitata)
- `GET /events` e `GET /leads` (token admin obbligatorio)
- `POST /catalog/sync` e `POST /energy/sync` (token admin obbligatorio)

## Pubblicazione catalogo

Il comando di progetto per arricchire e pubblicare il catalogo è:

```bash
python3 scripts/update_live_catalog.py --skip-enrich
# oppure, per includere l’arricchimento delle immagini:
python3 scripts/update_live_catalog.py
```

Aggiorna manifest, URL e risorse secondo la configurazione del publisher. Il mirror statico in `api/static/` deve essere rigenerato dal seed di bundle quando cambia la revisione; la policy confidence v1 ha riallineato seed e mirror al seed v77, senza pubblicare dati su CDN o servizi esterni.

## Sicurezza per deploy

L’API resta pensata per uso interno e sviluppo locale. Prima di renderla raggiungibile da Internet servono HTTPS, segreti gestiti fuori dal repository e rate limiting distribuito sul reverse proxy/WAF: il rate limit integrato è in memoria e vale per singolo processo, non sostituisce le protezioni per un servizio multi-worker. Non committare il token admin o database contenenti lead.

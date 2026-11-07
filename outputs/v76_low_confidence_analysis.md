# Cause dei 1.300 record con confidenceScore < 0,5 — v76

## Sintesi

Il problema principale non è la mancanza dei consumi: tutti i 1.300 record hanno i consumi necessari alla simulazione secondo le regole dell’app. Il punteggio basso riflette soprattutto **copertura EEA assente o non abbinata alla variante/anno esatto**, **stime per anni non coperti** e **dati storici pre-2010**. La classificazione sotto è basata sui testi `sourceName` presenti nel seed; non è una nuova verifica dei documenti sorgente.

- Record esaminati: **1.300** (ICE 970, EV 314, HEV 16).
- Punteggi: **0,30: 682**; **0,35: 166**; **0,40: 450**; **0,45: 2**.
- Anni modello: **682** pre-2010 (2005–2009), **19** dal 2020 al 2024, **599** nel 2025–2026. La concentrazione ai due estremi temporali coincide con le carenze di copertura indicate nelle fonti.
- `fieldSources` e `fieldSourceDates` sono assenti per tutti i 1.300 record; c’è un `sourceName` descrittivo, ma manca la tracciabilità per singolo campo che confermi l’origine del consumo specifico.
- Nessun record low-confidence ha un `imageURL`.

## Cause riportate in `sourceName`

- **Pre-2010: assenza copertura EEA IT; consumo stimato: 682 (52.5%)** — score 0.30; anni 2005–2009.
- **2026: proiezione da stessa variante 2025: 165 (12.7%)** — score 0.40; anni 2026–2026.
- **2025: nessun match EEA IT; stima: 142 (10.9%)** — score 0.40; anni 2025–2025.
- **EEA EU: versione non abbinata: 142 (10.9%)** — score 0.40; anni 2025–2025.
- **2026: fonte EEA disponibile non copre l’anno: 135 (10.4%)** — score 0.35; anni 2026–2026.
- **Ripristino: nessun match EEA IT affidabile: 26 (2.0%)** — score 0.35; anni 2022–2026.
- **Campione EEA n=1 debole; proxy variante sorella: 5 (0.4%)** — score 0.35; anni 2022–2026.
- **2026: fonte EEA 2023, dato datato: 1 (0.1%)** — score 0.45; anni 2026–2026.
- **2026: fonte EEA 2025 provvisoria: 1 (0.1%)** — score 0.45; anni 2026–2026.
- **EEA EU: versione non abbinata, con label OEM: 1 (0.1%)** — score 0.40; anni 2025–2025.

## Aggregazione per causa principale

- Pre-2010 senza copertura EEA IT: **682 (52.5%)**
- Copertura IT incompleta/trasferita a un altro anno: **444 (34.2%)**
- Versione EEA EU non abbinata esattamente: **143 (11.0%)**
- Ripristini senza match affidabile: **26 (2.0%)**
- Campione insufficiente/proxy variante: **5 (0.4%)**

## Lettura per tipo di veicolo

- **ICE (970):** prevalgono i record storici pre-2010 (677) e le stime/riporti a 2025–26. Nei casi moderni il problema è spesso l’assenza di un match EEA IT per anno/variante, non l’assenza del valore numerico.
- **EV (314):** 142 sono etichettate come EEA EU “Zr” con versione non abbinata e un ulteriore record aggiunge una label OEM; in totale sono **143**. Il resto è soprattutto stima per anno/variante non coperti. È un rischio di attribuzione all’allestimento corretto, anche se il kWh è presente.
- **HEV (16):** casi limitati, ma ricadono anch’essi in fonti non abbinate o anni non coperti; il gruppo ha un punteggio base differente nella funzione di scoring documentata.

## Problema del punteggio e auditabilità

Il repository contiene `scripts/enrich_catalog_quality_fields.py`, la cui funzione `confidence_for()` assegna punti per powertrain, dimensioni, consumi e immagine, ma non codifica la qualità del match della fonte o la copertura dell’anno. Applicando quella funzione ai 1.300 record, nessuno dei punteggi salvati coincide: il calcolo produce 0,85 per 1.284 ICE/EV e 0,50 per 16 HEV, contro valori salvati 0,30–0,45. Quindi il punteggio v76 **non è riproducibile con lo scorer versionato esaminato**: manca una definizione/calibrazione unica e verificabile.

Il `sourceUpdatedAt` è presente, ma in questi record assume tre date di aggiornamento del seed (2026-09-07: 985; 2026-10-23: 172; 2026-10-27: 143). Poiché `fieldSourceDates` è vuoto, non va interpretato come data del documento OEM/EEA che supporta il singolo valore.

## Implicazioni e priorità

1. **Priorità alta:** chiarire la semantica e rigenerare `confidenceScore` con un algoritmo versionato che distingua fonte ufficiale esatta, versione non abbinata, stima, proxy da anno precedente e assenza di dato.
2. **Priorità alta:** aggiungere `fieldSources`/`fieldSourceDates` per i consumi effettivamente usati, soprattutto per i 682 record pre-2010 e per i record 2025–26 estrapolati o non abbinati.
3. **Priorità media:** verificare in blocco i 143 EV con versione EEA EU non abbinata (uno ha anche una label OEM) e i 165 record 2026 stimati dalla stessa variante 2025, prima di presentare il dato come specifica esatta del modello.
4. **Priorità media:** ricercare fonti primarie per le famiglie pre-2010 e per i cinque casi basati su un campione EEA `n=1`/variante sorella; se non verificabili, mantenere visibile la dicitura “stima”.

Il CSV allegato conserva l’ID, la causa normalizzata, il `sourceName` originale, le date e i valori energetici per controlli record-per-record. Il seed e i mirror non sono stati modificati.

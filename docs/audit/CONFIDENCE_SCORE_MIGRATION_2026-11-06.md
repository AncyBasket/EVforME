# Migrazione confidenceScore v1 — 6 novembre 2026

## Esito

Applicata la policy deterministica v1 al catalogo: seed `v76 → v77`, **6.977 record**. Gli score precedenti sono conservati in `confidenceScoreLegacy`; ogni record ha ora `confidencePolicyVersion: 1` e un oggetto `confidenceEvidence` che espone causa, fonte classificata, relazione fra anno modello e anno fonte, match variante, campione, campi di calcolo richiesti e copertura di provenienza puntuale.

`confidenceScore` è definito come **indice ordinale di qualità dell’evidenza**, non come probabilità statistica. L’interfaccia ora lo chiama “Qualità dati …/100” e spiega che non rappresenta una probabilità. Il dettaglio della rubrica è in [CONFIDENCE_SCORE_POLICY_V1.md](CONFIDENCE_SCORE_POLICY_V1.md).

## Distribuzione e impatto

| Fascia UI | Score v1 | Record |
|---|---:|---:|
| Bassa | 0,30–0,45 | 2.283 |
| Media | 0,50–0,75 | 1.825 |
| Alta | 0,80–0,90 | 2.869 |

Prima della migrazione erano sotto 0,50 **1.300 record**; ora sono **2.283**. La differenza netta è +983. Il cambiamento deriva soprattutto da record che prima avevano uno score alto senza prova riproducibile del match di versione: **1.089 record EV** provenienti da `EEA co2cars EU Zr` risultano ora nella categoria “versione EEA non abbinata” (0,40). Questo non afferma che ogni misura sia errata: indica che l’identità esatta della variante non è provata dai metadati attuali. Occorre verificare gli abbinamenti OEM/EEA per rialzare quei punteggi.

Altre cause principali sotto 0,50: 682 stime pre-2010 senza copertura indicata, 344 stime o mancati match EEA IT, 161 casi stantii/non coperti, 5 proxy da variante sorella con campione `n=1` e 2 record EEA IT con anno non allineato.

Sono cambiati **4.085 score** rispetto al legacy. La transizione di fascia è: dei 1.300 legacy bassi, 1.299 restano bassi; dei legacy medi, 17 scendono a basso; dei legacy alti, 967 scendono a basso, 256 a medio e 2.771 restano alti. Il valore legacy resta disponibile per confronto e rollback analitico.

## File e comportamento

- Policy condivisa: `scripts/catalog_confidence.py`.
- Migrazione ripetibile: `scripts/recalculate_catalog_confidence.py` (preview senza flag; `--write` per sincronizzare).
- Test riproducibilità: `scripts/test_catalog_confidence.py`.
- Il generatore quality e le pipeline catalogo aggiornate usano lo stesso scorer, non più formule basate su immagini/dimensioni o valori hardcoded.
- Seed bundle, mirror API leggibile/minificato e manifest sono allineati: versione 77, 6.977 righe, 7.477.026 byte.
- SQLite conserva score corrente, legacy, versione e evidence JSON; `GET /catalog/export` li espone.
- Il client Swift decodifica l’evidence e mantiene il warning per gli score bassi, ora spiegato come qualità dati.

## Verifiche

- Policy e dataset: **12 test superati**, inclusa verifica riga per riga di tutti i 6.977 score.
- Backend API/database: **8 test superati**, incluso export del nuovo evidence.
- `py_compile` sui moduli modificati: superato.
- Localizzazioni (`plutil`), `git diff --check`, parità dei tre cataloghi e manifest v77: superati.
- `swiftc -frontend -parse` sui file Swift modificati e test correlati: superato.

XCTest è stato tentato sul simulatore disponibile, ma non ha completato la build: il server macro Apple restituisce una risposta malformata per `SwiftUIMacros.StateMacro` e `PreviewsMacros.SwiftUIView`; la policy locale ha inoltre negato la scrittura alla directory di sicurezza SwiftPM. Non è quindi un esito XCTest verde e non consente di confermare il type-check completo dell’app. La compilazione ricorsiva di tutti gli script storici con `compileall` è stata ostacolata da errori filesystem `Resource deadlock avoided`; i moduli Python toccati sono stati compilati singolarmente con successo.

## Limite sostanziale

La migrazione rende **riproducibile il punteggio**, non certifica la verità di ciascun valore tecnico. `confidenceEvidence.evidenceScope` distingue provenance a livello record da quella parziale per campo. Per migliorare l’affidabilità materiale, la prossima tranche dovrebbe aggiungere URL e date OEM/EEA ai campi di consumo richiesti e chiudere i match variante, soprattutto per i 1.089 EV EEA EU non abbinati.

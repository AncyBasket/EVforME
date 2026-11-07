# Policy confidenceScore v2 — indice di qualità/copertura

## Semantica (obbligatoria)

`confidenceScore` è un **indice ordinale di qualità e copertura della provenienza** in `[0, 1]`.

Non è:

- una probabilità di correttezza del consumo o della scheda;
- una certificazione ufficiale costruttore;
- una prova che anno, variante o mercato siano validati.

Nell’UI va descritto come **qualità/copertura dati** (es. “Data quality N/100”), non come “confidenza %”.

## Tre stati di evidenza

Ogni campo di calcolo richiesto dal powertrain ricade in uno di:

| Stato | Significato |
|---|---|
| `missing` | Valore nil **oppure** nessuna provenienza puntuale |
| `provenance_unverified` | Valore presente e stringa fonte/data non vuota, **senza** prova documentale verificata in pipeline |
| `verified` | Solo se un passaggio di verifica documentale esplicito lo ha marcato (questa PR **non** inventa verifiche retroattive) |

Regole:

1. **Campo nil ⇒ non coperto**, anche se `fieldSources` / `fieldSourceDates` hanno una chiave.
2. **Fonte/data non vuote ≠ validità** di anno, variante, mercato o correttezza del numero.
3. **`officialMatched == true` da solo non abilita** lo stato `verified` né il tier massimo.
4. URL generici / live per anni passati / date incompatibili col model year **declassano** la provenienza (riuso dei validatori `scripts/lib/phev_manus_v76_validate.py`), senza promuovere altri record.

## Rubrica v2 (discreta)

| Motivo | Score | Note |
|---|---:|---|
| Provenienza puntuale su tutti i campi richiesti (valori non nil) + date coerenti col model year | 0,80 | Copertura completa **non verificata** documentally |
| Provenienza puntuale parziale | 0,70 | Alcuni campi ancora `missing` |
| EEA IT anno esatto, campione `n≥5`, non provvisorio | 0,85 | Record-level ufficiale |
| EEA IT anno esatto senza `n` | 0,75 | |
| EEA IT anno esatto, `n<5` | 0,65 | |
| EEA IT anno esatto provvisorio | 0,70 | |
| EEA WLTP / EPA / importatore / OEM-listino a livello record | 0,80–0,90 | Non implica verifica campo |
| Derivazione omologativa dichiarata (`dataDerivedFromSameHomologationYear` / same homolog) | 0,70 | Provenienza dichiarata, non certificazione |
| EEA IT un anno prima / più vecchio | 0,45 / 0,35 | |
| EU unmatched / stima / proxy n=1 / pre-2010 | 0,30–0,40 | |
| Riferimento locale generico (`IT-common`) | 0,50 | |
| Sconosciuto | 0,35 | |

I valori sono **livelli di rubrica**, non probabilità. Cambiare soglie ⇒ incrementare `POLICY_VERSION`, aggiornare test e ricalcolare.

## Cosa non fa questa policy

- Non ricalcola consumi, batterie, autonomie o fonti tecniche.
- Non marca `verified` retroattivamente per alzare gli score.
- Non tocca formule PHEV, API, privacy o deploy.

## Riproduzione

```bash
python3 scripts/recalculate_catalog_confidence.py          # preview
python3 scripts/recalculate_catalog_confidence.py --write # seedVersion +1, mirrors
python3 -m unittest scripts.test_catalog_confidence -v
```

# Policy confidenceScore v1

## Semantica

`confidenceScore` è un **indice ordinale di qualità dell’evidenza** compreso tra 0 e 1. Non è una probabilità calibrata e non significa, per esempio, “85% di probabilità che il consumo sia corretto”. Nell’interfaccia viene mostrato come indice su 100 e in bande qualitativa alta/media/bassa.

La policy è implementata in `scripts/catalog_confidence.py`. Ogni record conserva `confidencePolicyVersion`, `confidenceEvidence` e il valore precedente in `confidenceScoreLegacy`. Lo scorer non legge mai `confidenceScore` né `confidenceScoreLegacy`: ripete lo stesso risultato a partire da anno, fonte, campione, stato provvisorio, match dichiarato e provenienze puntuali già presenti.

## Rubrica v1

| Evidenza | Score | Interpretazione |
|---|---:|---|
| Fonte per ogni campo di calcolo, data per ogni fonte e match ufficiale esatto | 0,95 | Evidenza puntuale più forte disponibile |
| Fonte per tutti i campi di calcolo, ma senza tutti i requisiti di match/data | 0,90 | Provenienza puntuale completa, match non pienamente confermato |
| Fonte per almeno un campo, ma copertura parziale dei campi di calcolo | 0,75 | Provenienza puntuale parziale |
| Etichetta variante OEM ufficiale ma misura EEA non abbinata | 0,75 | Identità del modello meglio definita del dato di consumo |
| EEA IT per anno esatto e campione `n >= 5`, non provvisorio | 0,85 | Fonte ufficiale annuale, a livello record |
| EEA WLTP a livello record, senza provenienza puntuale | 0,80 | Fonte di ciclo ufficiale, mapping campo non completo |
| Importatore ufficiale WLTP, fonte OEM/listino o fonte EPA | 0,80–0,90 | Fonte ufficiale; la variante/campo può richiedere controllo |
| EEA IT stessa annualità provvisoria | 0,70 | Evidenza ufficiale ma provvisoria |
| EEA IT senza campione dichiarato | 0,75 | Evidenza annuale, numerosità non verificabile |
| EEA IT con `n < 5` | 0,65 | Campione limitato |
| EEA NEDC | 0,65 | Fonte ufficiale, ciclo di omologazione meno comparabile al WLTP |
| Riferimento locale generico (es. `IT-common`) | 0,50 | Stima/benchmark non documentato come scheda specifica |
| EEA EU con versione non abbinata | 0,40 | Dato ufficiale ma match insufficiente per attribuzione esatta |
| EEA IT di un anno precedente | 0,45; se più vecchio 0,35 | Fonte non allineata all’anno modello |
| Stima senza match, fonte non coprente o ripristino non verificato | 0,35–0,40 | Dato utilizzabile solo come stima/indicazione |
| Proxy da variante sorella con `n=1` | 0,35 | Evidenza campionaria insufficiente |
| Pre-2010 senza copertura EEA IT indicata | 0,30 | Stima storica non verificata |

I valori sono livelli discreti di rubriche, non percentuali statistiche. Per cambiare soglie o interpretazione si incrementa `POLICY_VERSION`, si aggiornano i test e si rigenera l’intero catalogo.

## Provenienza per campo

`fieldSources` e `fieldSourceDates` restano la fonte di verità per i campi puntualmente documentati. Lo scorer li usa soltanto quando la chiave coincide con un campo di calcolo richiesto dal powertrain. Non crea URL, date o attribuzioni non presenti. `confidenceEvidence.evidenceScope` dichiara `record_level` o `partly_field_level`; quindi le etichette `sourceName` non vengono spacciate per citazioni per singolo campo.

Per completare la tracciabilità mancante occorre verificare fonti OEM/EEA e aggiungere le mappe per ciascun campo, con data del documento. È un’attività di arricchimento separata: questa migrazione corregge la riproducibilità, non certifica da sola la correttezza di ogni consumo.

## Migrazione e riproduzione

La migrazione conserva lo score precedente in `confidenceScoreLegacy`, ricalcola il nuovo score e salva l’evidenza strutturata. Si esegue prima una preview e poi, dopo i controlli:

```bash
python3 scripts/recalculate_catalog_confidence.py
python3 scripts/recalculate_catalog_confidence.py --write
python3 -m unittest scripts.test_catalog_confidence -v
python3 -m unittest discover -s api -p 'test_*.py' -v
```

`--write` incrementa `seedVersion`, aggiorna byte count e timestamp, e sincronizza seed, mirror API minificato e leggibile e manifest locali. Il DB API ricarica il seed al successivo avvio perché la versione cambia.

## Garanzie di test

- scoring indipendente dai punteggi legacy e deterministico;
- un test per ogni causa critica (pre-2010, anno precedente, versione EEA non abbinata, `n=1`, provvisorio, fonte puntuale); 
- verifica riga per riga che seed e score si ricostruiscano dalla policy dichiarata;
- confronto dei tre cataloghi e dei manifest dopo la migrazione.

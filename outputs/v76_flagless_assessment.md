# Valutazione dei record senza flag di completezza — v76

## Esito

Tutti i **6.855** record senza `catalogDataIncomplete` hanno i consumi non ponderati richiesti per la simulazione ordinaria: ICE/HEV con carburante positivo e BEV con energia positiva. Per il sottoinsieme EV è presente energia diretta `energyConsumptionKWhPerKm`; non è stato necessario usare un valore ponderato. Questo significa **calcolabili sui consumi**, non necessariamente completi o verificati in ogni campo.

## Ripartizione e verifiche

- Versione catalogo: **v76**, 6,977 record complessivi.
- Senza flag: **6,855** — ICE 4,884, HEV 140, EV 1,831; nessun PHEV senza flag.
- Con i soli campi consumi necessari mancanti/invalidi: **0** su 6,855.
- Confidence inferiore a 0,5: **1,300** (19.0%); ICE 970, HEV 16, EV 314.
- Provenienza per singolo campo (`fieldSources`) assente: **6,855**. I campi generali `sourceName` e `sourceUpdatedAt` sono invece presenti in tutti questi record.
- Immagine (`imageURL`) assente: **6,855**.
- Record termici non-EV con tassa catalogo zero e senza potenza catalogo per una stima regionale: **14**.
- EV con bollo zero, anno modello 2021 o precedente: **350**; dopo la scadenza dell’esenzione il costo effettivo dipende da regione, data di immatricolazione e potenza P.2 inserita dall’utente.

## Criterio usato

Il criterio per i consumi segue il codice dell’app: ICE/HEV richiedono carburante `fuelConsumptionLPerKm` positivo; EV richiede `energyConsumptionKWhPerKm` positivo e non marcato ponderato, oppure WLTP elettrico non ponderato positivo. La regola `energyIsWeighted` esclude un valore aggregato PHEV dal consumo in modalità elettrica. Il sottoinsieme senza flag non contiene PHEV.

La valutazione non certifica che il numero sia esatto per ogni allestimento o anno: non tutti i record hanno fonti per campo e oltre mille hanno confidence bassa. Il CSV allegato permette di filtrare i singoli casi e vedere i consumi, confidence e caveat sul bollo.

## Interpretazione

Per i consumi, i 6.855 record possono essere usati dalla simulazione senza override. Non sono però tutti “completi” in senso documentale: **1.300** hanno confidence sotto 0,5 e **tutti** sono privi di provenance puntuale per campo e di URL immagine. Inoltre le **14** auto termiche con tassa zero e senza kW catalogo possono produrre una stima del costo totale priva di bollo noto; i **350** EV più vecchi elencati richiedono verifica del bollo post-esenzione secondo i dati dell’utente.

Il controllo è stato in sola lettura: seed, manifest e mirror non sono stati modificati.

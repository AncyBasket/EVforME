# Follow-up audit tecnico — 3 novembre 2026

## Correzioni applicate

- **Versione seed iOS:** `VehicleCatalogService` legge `seedVersion` dal manifest incluso nel bundle. Se il manifest manca o è invalido, la cache viene considerata non valida. Un test confronta versione e conteggio righe del manifest con il seed effettivamente incluso.
- **Mirror API:** l’API confronta la revisione e il conteggio del manifest con il proprio stato e riallinea il DB veicoli al seed al successivo avvio quando differiscono.
- **PHEV senza autonomia:** eliminato il fallback arbitrario di 50 km. Il range deriva dal WLTP oppure da batteria/consumo charge-depleting; se nessuno dei due è disponibile, la quota elettrica è limitata al minimo prudenziale del 10% e il verdetto lo dichiara esplicitamente. L’estimatore delle ricariche non inventa un’autonomia.
- **Dati a bassa confidenza:** il verdetto ora mostra un avviso se uno dei due veicoli selezionati ha confidence score sotto 0,5; resta necessario verificare le specifiche sui documenti del veicolo.
- **API lead/eventi:** le letture e le rotte di sync richiedono un bearer token admin di almeno 32 caratteri; le scritture validano i dati, richiedono consenso esplicito per i lead, rifiutano campi personali comuni negli analytics, limitano dimensione e frequenza delle richieste e cancellano lead/eventi oltre la retention configurata (180 giorni di default).
- **Catalogo statico API:** i file statici versionati sono stati rigenerati dal seed v75 incluso nel progetto. Non è stato pubblicato nulla su CDN o servizi esterni.
- **Documentazione:** il report del 27 ottobre è marcato come storico; la privacy policy, il manuale API e il README sono aggiornati.

## Limiti ancora aperti

La correzione tecnica non certifica la veridicità di ogni dato del catalogo. Nel seed v75 analizzato: 171 righe EV dichiarano una stima come fonte; 314 righe EV hanno confidence score inferiore a 0,5; 118 dei 121 record PHEV sono marcati incompleti. Questi valori vanno verificati contro schede omologative e documentazione dei costruttori, senza interpolare o inventare specifiche. Il selettore e il verdetto mostrano note di qualità, ma un audit delle fonti modello per modello resta necessario.

La protezione anti-abuso per gli endpoint pubblici di ingestione è in memoria e per singolo processo: l’API resta destinata a uso locale/interno. Prima di un’esposizione Internet servono HTTPS, gestione sicura del segreto e rate limiting centralizzato su reverse proxy/WAF.

## Verifica

- Test backend: `python3 -m unittest discover -s api -p 'test_*.py'` — **7/7 passati**; sintassi Python e parità dei mirror statici v75 verificate.
- L’ultimo tentativo XCTest con Xcode 27.2 si è fermato prima di eseguire i test: `swift-plugin-server` ha restituito una risposta malformata per le macro SwiftUI `State` e `Preview`. Questo problema di toolchain non è stato corretto dal codice del progetto; la suite iOS va rieseguita su un Xcode funzionante.

# Post-Manus follow-ups (dopo PR dati v76)

Salvataggio WIP: PR #33 (`wip/save-2026-11-07-recon`) resta DRAFT — non mergiare.
Questa nota non implementa nulla: solo dipendenze per PR successive.
Niente wave4 finché non chiesto.

## A. Confidence + decoder/copy

**Dipende da:** merge revisione PR dati v76 (questo filone).

- Distinguere punteggio rubrica da verifica documentale.
- Lo scorer non deve trattare `fieldSources` / `fieldSourceDates` non vuoti come prova di correttezza, anno o variante.
- Aggiornare copy/decoder di conseguenza; nessun ricalcolo massivo nel PR dati.

## B. Logica PHEV (Core)

**Dipende da:** A (copy/confidence coerenti) o almeno review indipendente dei gate.

- Revisionare autonomia derivata e fallback minimo 10% elettrico.
- Verificare gate UI e simulatore: nessun verdetto con dati richiesti mancanti.
- Il fallback nel diff WIP non dimostra da solo che il gate venga aggirato — serve test mirato.

## C. API / security / privacy + cataloghi generati

**Dipende da:** B se tocca payload/retention condivisi; altrimenti parallelo dopo A.

- Verificare sincronizzazione seed↔API e retention effettiva.
- Non promettere cancellazione puntuale a 180 giorni se avviene solo ad avvio o su richiesta.
- Nessun deploy in queste PR.

# Stato di completezza del catalogo v76

**Fonte analizzata:** `EVforME?/Data/vehicles.seed.quality.json`, verificata contro `EVforME?/Data/catalog_cdn.json`. Il controllo è in sola lettura: seed e mirror non sono stati modificati.

- **Versione:** v76 (manifest aggiornato 2026-11-03T10:08:00+00:00).
- **Righe catalogo:** 6,977.
- **Record marcati `catalogDataIncomplete: true`:** 119 (1.71%).
- **Record incompleti PHEV:** 118; **EV:** 1.
- **Flag false:** 3; **flag assente/null:** 6855. L’assenza del flag non è stata interpretata come completezza.

## Campi mancanti nei record marcati incompleti

Conteggi per campo; un record può contribuire a più voci:
- `energyConsumptionKWhPerKm`: 111
- `fuelConsumptionLPerKm`: 94
- `batteryKWh`: 91
- `wltpRangeKm`: 86

## Record incompleti per marca

- BMW: 18
- Audi: 15
- Mercedes-Benz: 15
- Jeep: 11
- Volvo: 5
- CUPRA: 4
- Hyundai: 4
- Peugeot: 4
- Toyota: 4
- Volkswagen: 4
- Alfa Romeo: 3
- DS: 3
- Ford: 3
- Lexus: 3
- MG: 3
- Porsche: 3
- Citroën: 2
- Kia: 2
- Land Rover: 2
- Mazda: 2
- MINI: 2
- Renault: 2
- BYD: 1
- Chevrolet: 1
- Honda: 1
- Mitsubishi: 1
- Opel: 1

## Avanzamento della ricerca PHEV

La ricerca della tranche delle **45 famiglie PHEV residue** è stata eseguita; gli esiti provengono da ricerche separate e non equivalgono a 45 famiglie con dati utilizzabili per ogni campo. I risultati della seconda tranche non sono stati integrati nel seed v76. I 118 record PHEV ancora marcati incompleti sono quindi la misura dello stato effettivo del catalogo, non un conteggio di sole ricerche non eseguite.

Un record può contenere già valori utili e restare incompleto perché mancano uno o più campi richiesti dal calcolo. Per esempio, la Toyota C-HR PHEV 2024 ha batteria, autonomia e CO₂, ma resta marcata incompleta perché manca `energyConsumptionKWhPerKm`; il consumo elettrico ponderato non è stato trattato come consumo in modalità elettrica pura.

Il manifest v76 dichiara che i consumi ponderati restano informativi e che non sono stati inferiti valori charge-sustaining o charge-depleting. L’elenco record completo, con ID, campi mancanti e valori già presenti, è nel CSV `v76_incomplete_records.csv`.

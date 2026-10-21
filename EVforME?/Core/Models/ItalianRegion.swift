//
//  ItalianRegion.swift
//  EVforME?
//
//  Tariffari ACI / regionali bollo 2026 (opzionale).
//

import Foundation

/// Regione / provincia autonoma per stima bollo EV e, dove citato, bollo termico.
enum ItalianRegion: String, CaseIterable, Identifiable, Codable {
    case unspecified
    case lombardia
    case piemonte
    case lazio
    case emiliaRomagna
    case toscana
    case abruzzo
    case campania
    case molise
    case bolzano
    case basilicata
    case puglia
    case sicilia
    case umbria
    case valleDAosta
    /// Altre regioni senza tariffa EV ufficiale in-app → non stimato.
    case otherUnknown

    var id: String { rawValue }

    var title: String {
        switch self {
        case .unspecified: return L10n.italianRegionUnspecified
        case .lombardia: return "Lombardia"
        case .piemonte: return "Piemonte"
        case .lazio: return "Lazio"
        case .emiliaRomagna: return "Emilia-Romagna"
        case .toscana: return "Toscana"
        case .abruzzo: return "Abruzzo"
        case .campania: return "Campania"
        case .molise: return "Molise"
        case .bolzano: return "Bolzano"
        case .basilicata: return "Basilicata"
        case .puglia: return "Puglia"
        case .sicilia: return "Sicilia"
        case .umbria: return "Umbria"
        case .valleDAosta: return "Valle d'Aosta"
        case .otherUnknown: return L10n.italianRegionOtherUnknown
        }
    }

    /// Anni di esenzione bollo EV dall’immatricolazione (oltre a Lombardia/Piemonte = permanente).
    /// Valle d’Aosta: 8 anni per EV immatricolate dal 2019 (tariffario ACI 2026).
    /// Altrove: regola nazionale tipica 5 anni.
    var evExemptionYears: Int {
        switch self {
        case .lombardia, .piemonte:
            return Int.max
        case .valleDAosta:
            return 8
        default:
            return 5
        }
    }

    /// `true` se l’esenzione VdA a 8 anni non applica (immatricolazione pre-2019) → usa 5 anni.
    func evExemptionYears(forVehicleYear vehicleYear: Int) -> Int {
        if self == .valleDAosta {
            return vehicleYear >= 2019 ? 8 : 5
        }
        return evExemptionYears
    }

    /// €/kW dopo esenzione. `nil` = non stimato. Lombardia/Piemonte: 0 permanente.
    ///
    /// Bolzano 1,96 €/kW: tariffa Euro 6 (Euro 0–5: 1,99 €/kW — non modellato senza classe Euro).
    /// Molise 2,76 €/kW: Regione Molise Tariffario 2026 (riportato da Quattroruote, guida bollo Molise
    /// aggiornata al 17/02/2026) — EV esenti 5 anni, poi 1/4 della tariffa Euro 4/5/6 ≤100 kW (2,76),
    /// lineare anche oltre 100 kW.
    /// Sicilia: clausola ACI «a prescindere» sull’importo benzina a 2,58 €/kW; in-app 2,58 × 1/4 post-esenzione.
    var evBolloEURPerKw: Double? {
        switch self {
        case .unspecified:
            // Stima nazionale di ripiego quando l’utente non sceglie regione.
            return 2.58
        case .lombardia, .piemonte:
            return 0
        case .lazio, .emiliaRomagna:
            return 2.84
        case .toscana:
            return 2.71
        case .abruzzo, .campania:
            return 3.12
        case .molise:
            // Regione Molise Tariffario 2026 (Quattroruote, 17/02/2026): Euro 4/5/6 ≤100 kW = 2,76 €/kW.
            return 2.76
        case .bolzano:
            // Euro 6: 1,96 €/kW (Euro 0–5: 1,99 — non usato senza classe Euro).
            return 1.96
        case .basilicata, .puglia, .umbria:
            return 2.58
        case .sicilia:
            // Clausola «a prescindere»: 1/4 dell’importo calcolato a 2,58 €/kW (scala benzina nazionale).
            return 2.58
        case .valleDAosta:
            // Dopo gli 8 anni di esenzione (EV ≥2019): stima nazionale 2,58.
            return 2.58
        case .otherUnknown:
            return nil
        }
    }

    /// Esenzione permanente (anche dopo i primi anni).
    var evPermanentlyExempt: Bool {
        self == .lombardia || self == .piemonte
    }

    /// `true` se in-app c’è un tariffario termico 2026 citato (altrimenti stima nazionale catalogo).
    var hasCitedThermalBolloTariff: Bool {
        self == .molise
    }

    /// Bollo termico (ICE/HEV/PHEV) con tariffario regionale 2026 citato.
    ///
    /// Molise (Regione Molise Tariffario 2026, Quattroruote 17/02/2026), Euro 4/5/6:
    /// - benzina/diesel: 2,76 €/kW fino a 100 kW + 4,14 €/kW oltre;
    /// - solo GPL o solo metano: 1/4 di 2,76 €/kW (lineare);
    /// - bifuel GPL/metano–benzina: non modellato (manca `FuelKind` bifuel) → stima nazionale.
    func thermalBolloEUR(powerKw: Double, fuelKind: FuelKind) -> Double? {
        guard powerKw > 0 else { return nil }
        switch self {
        case .molise:
            switch fuelKind {
            case .lpg, .cng:
                let raw = 2.76 * 0.25 * powerKw
                return (raw * 100).rounded() / 100
            case .petrol, .diesel, .unknown:
                let raw = 2.76 * min(powerKw, 100) + 4.14 * max(0, powerKw - 100)
                return (raw * 100).rounded() / 100
            }
        default:
            return nil
        }
    }

    /// Nota leggibile su stime / caveat regionali (Localizable IT/EN).
    var evBolloRateNote: String? {
        switch self {
        case .molise:
            return L10n.italianRegionBolloNoteMolise
        case .bolzano:
            return L10n.italianRegionBolloNoteBolzano
        case .sicilia:
            return L10n.italianRegionBolloNoteSicilia
        case .valleDAosta:
            return L10n.italianRegionBolloNoteValleDAosta
        default:
            return nil
        }
    }

    /// Nota sotto il picker: caveat EV regionali, oppure avviso stima nazionale sul termico.
    var bolloPickerNote: String? {
        if let ev = evBolloRateNote { return ev }
        if hasCitedThermalBolloTariff { return nil }
        if self == .otherUnknown { return nil }
        return L10n.italianRegionBolloNoteNationalThermal
    }
}

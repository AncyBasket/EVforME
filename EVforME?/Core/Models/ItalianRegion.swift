//
//  ItalianRegion.swift
//  EVforME?
//
//  Tariffari ACI bollo EV 2026 (opzionale). Fonte: tariffari ACI regionali 2026.
//

import Foundation

/// Regione / provincia autonoma per stima bollo EV (tariffa €/kW dopo l’esenzione).
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
    /// Molise 3,12: allineato ad Abruzzo/Campania; senza conferma esplicita tariffario ACI Molise 2026 → stima.
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
            // Stima (stesso cluster Abruzzo/Campania); fonte ACI Molise 2026 non verificata in-app.
            return 3.12
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
}

//
//  ItalianRegion.swift
//  EVforME?
//
//  Tariffari ACI bollo EV 2026 (opzionale). Fonte: tariffari ACI regionali.
//

import Foundation

/// Regione / provincia autonoma per stima bollo EV (tariffa €/kW dopo i 5 anni).
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

    /// €/kW dopo esenzione 5 anni. `nil` = non stimato. Lombardia/Piemonte: 0 permanente.
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
        case .abruzzo, .campania, .molise:
            return 3.12
        case .bolzano:
            return 1.96
        case .basilicata, .puglia, .sicilia, .umbria, .valleDAosta:
            return 2.58
        case .otherUnknown:
            return nil
        }
    }

    /// Esenzione permanente (anche dopo 5 anni).
    var evPermanentlyExempt: Bool {
        self == .lombardia || self == .piemonte
    }
}

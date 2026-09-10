//
//  VehicleProfile.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

struct VehicleDimensions {
    let lengthM: Double
    let widthM: Double
    let heightM: Double
}

/// Veicolo attuale dell'utente (partenza confronto).
enum SourceVehicleProfile: String, CaseIterable, Identifiable {
    case notSelected
    case iceCompact
    case iceSuv

    var id: String { rawValue }

    var title: String {
        switch self {
        case .notSelected: return L10n.vehicleNotSelected
        case .iceCompact: return L10n.vehicleIceCompact
        case .iceSuv: return L10n.vehicleIceSuv
        }
    }

    var dimensions: VehicleDimensions {
        switch self {
        case .notSelected: return VehicleDimensions(lengthM: 0, widthM: 0, heightM: 0)
        case .iceCompact: return VehicleDimensions(lengthM: 4.25, widthM: 1.78, heightM: 1.46)
        case .iceSuv: return VehicleDimensions(lengthM: 4.68, widthM: 1.9, heightM: 1.68)
        }
    }

    var dimensionsText: String {
        if self == .notSelected {
            return L10n.vehicleDimensionsNotSelected
        }
        return L10n.vehicleDimensionsFormat(dimensions.lengthM, dimensions.widthM, dimensions.heightM)
    }

    /// Litri/km medi.
    var fuelConsumptionPerKm: Double {
        switch self {
        case .notSelected: return 0
        case .iceCompact: return 0.055
        case .iceSuv: return 0.08
        }
    }

    var maintenancePerYear: Double {
        switch self {
        case .notSelected: return 0
        case .iceCompact: return 520
        case .iceSuv: return 720
        }
    }

    var taxesPerYear: Double {
        switch self {
        case .notSelected: return 0
        case .iceCompact: return 180
        case .iceSuv: return 260
        }
    }
}

/// EV che l'utente vuole valutare come alternativa.
enum TargetEVProfile: String, CaseIterable, Identifiable {
    case notSelected
    case evCompact
    case evSuv

    var id: String { rawValue }

    var title: String {
        switch self {
        case .notSelected: return L10n.vehicleNotSelected
        case .evCompact: return L10n.vehicleEvCompact
        case .evSuv: return L10n.vehicleEvSuv
        }
    }

    var dimensions: VehicleDimensions {
        switch self {
        case .notSelected: return VehicleDimensions(lengthM: 0, widthM: 0, heightM: 0)
        case .evCompact: return VehicleDimensions(lengthM: 4.3, widthM: 1.82, heightM: 1.5)
        case .evSuv: return VehicleDimensions(lengthM: 4.75, widthM: 1.93, heightM: 1.66)
        }
    }

    var dimensionsText: String {
        if self == .notSelected {
            return L10n.vehicleDimensionsNotSelected
        }
        return L10n.vehicleDimensionsFormat(dimensions.lengthM, dimensions.widthM, dimensions.heightM)
    }

    /// kWh/km medi.
    var energyConsumptionPerKm: Double {
        switch self {
        case .notSelected: return 0
        case .evCompact: return 0.145
        case .evSuv: return 0.2
        }
    }

    var maintenancePerYear: Double {
        switch self {
        case .notSelected: return 0
        case .evCompact: return 220
        case .evSuv: return 320
        }
    }

    var taxesPerYear: Double {
        switch self {
        case .notSelected: return 0
        case .evCompact: return 0
        case .evSuv: return 0
        }
    }
}

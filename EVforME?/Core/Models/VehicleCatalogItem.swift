//
//  VehicleCatalogItem.swift
//  EVforME?
//

import Foundation

enum Powertrain: String, Codable {
    case ice
    case ev
    case phev

    /// Auto attuale: termica o ibrida plug-in.
    var isSourceCandidate: Bool {
        switch self {
        case .ice, .phev: return true
        case .ev: return false
        }
    }

    /// Target elettrificato: BEV o PHEV.
    var isTargetCandidate: Bool {
        switch self {
        case .ev, .phev: return true
        case .ice: return false
        }
    }
}

struct VehicleCatalogItem: Codable, Identifiable, Equatable {
    let id: String
    let brand: String
    let model: String
    let year: Int
    let powertrain: Powertrain
    let lengthM: Double
    let widthM: Double
    let heightM: Double
    let fuelConsumptionLPerKm: Double?
    let energyConsumptionKWhPerKm: Double?
    let maintenancePerYear: Double
    let taxesPerYear: Double
    let imageURL: String?

    // Playbook quality (opzionali, backward-compatible).
    let trim: String?
    let batteryKWh: Double?
    let wltpRangeKm: Int?
    let wltpConsumptionKWh100km: Double?
    let co2gKm: Double?
    let market: String?
    let sourceName: String?
    let sourceUpdatedAt: String?
    let confidenceScore: Double?

    var displayName: String {
        if let trim, !trim.isEmpty {
            return "\(brand) \(model) \(trim) (\(year))"
        }
        return "\(brand) \(model) (\(year))"
    }

    var dimensionsText: String {
        L10n.vehicleDimensionsFormat(lengthM, widthM, heightM)
    }

    var qualitySubtitle: String? {
        var parts: [String] = []
        if let confidenceScore {
            parts.append(String(format: "%.0f%%", confidenceScore * 100))
        }
        if let sourceName, !sourceName.isEmpty {
            parts.append(sourceName)
        }
        if let batteryKWh {
            parts.append(String(format: "%.0f kWh", batteryKWh))
        }
        if let wltpRangeKm {
            parts.append("\(wltpRangeKm) km")
        }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    /// URL per l’immagine in UI: solo HTTPS affidabili (Wikimedia). Scarta Unsplash morto.
    var heroImageURL: URL? {
        guard let raw = imageURL?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty,
              let u = URL(string: raw), u.scheme == "http" || u.scheme == "https" else {
            return nil
        }
        if let host = u.host?.lowercased(), host.contains("source.unsplash.com") {
            return nil
        }
        return u
    }

    /// Consumo EV effettivo: override catalogo, altrimenti WLTP/100.
    var resolvedEnergyKWhPerKm: Double? {
        if let energyConsumptionKWhPerKm { return energyConsumptionKWhPerKm }
        if let wltp = wltpConsumptionKWh100km { return wltp / 100.0 }
        return nil
    }

    /// Quota km elettrici stimata per PHEV (0…1).
    func phevElectricKmShare(hasHomeCharging: Bool) -> Double {
        guard powertrain == .phev else { return powertrain == .ev ? 1 : 0 }
        return hasHomeCharging ? 0.55 : 0.30
    }

    init(
        id: String,
        brand: String,
        model: String,
        year: Int,
        powertrain: Powertrain,
        lengthM: Double,
        widthM: Double,
        heightM: Double,
        fuelConsumptionLPerKm: Double?,
        energyConsumptionKWhPerKm: Double?,
        maintenancePerYear: Double,
        taxesPerYear: Double,
        imageURL: String?,
        trim: String? = nil,
        batteryKWh: Double? = nil,
        wltpRangeKm: Int? = nil,
        wltpConsumptionKWh100km: Double? = nil,
        co2gKm: Double? = nil,
        market: String? = "IT",
        sourceName: String? = nil,
        sourceUpdatedAt: String? = nil,
        confidenceScore: Double? = nil
    ) {
        self.id = id
        self.brand = brand
        self.model = model
        self.year = year
        self.powertrain = powertrain
        self.lengthM = lengthM
        self.widthM = widthM
        self.heightM = heightM
        self.fuelConsumptionLPerKm = fuelConsumptionLPerKm
        self.energyConsumptionKWhPerKm = energyConsumptionKWhPerKm
        self.maintenancePerYear = maintenancePerYear
        self.taxesPerYear = taxesPerYear
        self.imageURL = imageURL
        self.trim = trim
        self.batteryKWh = batteryKWh
        self.wltpRangeKm = wltpRangeKm
        self.wltpConsumptionKWh100km = wltpConsumptionKWh100km
        self.co2gKm = co2gKm
        self.market = market
        self.sourceName = sourceName
        self.sourceUpdatedAt = sourceUpdatedAt
        self.confidenceScore = confidenceScore
    }
}

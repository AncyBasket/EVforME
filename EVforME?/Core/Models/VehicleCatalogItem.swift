//
//  VehicleCatalogItem.swift
//  EVforME?
//

import Foundation

enum Powertrain: String, Codable {
    case ice
    case hev
    case ev
    case phev

    /// Auto attuale: termica, full hybrid o plug-in.
    var isSourceCandidate: Bool {
        switch self {
        case .ice, .hev, .phev: return true
        case .ev: return false
        }
    }

    /// Target elettrificato: BEV o PHEV (non HEV).
    var isTargetCandidate: Bool {
        switch self {
        case .ev, .phev: return true
        case .ice, .hev: return false
        }
    }

    /// Usa carburante liquido/gassoso (niente sola ricarica).
    var burnsFuel: Bool {
        switch self {
        case .ice, .hev, .phev: return true
        case .ev: return false
        }
    }
}

/// Carburante (ICE/HEV/PHEV). Opzionale nel seed; altrimenti euristica IT.
enum FuelKind: String, Codable {
    case petrol
    case diesel
    /// GPL — prezzo €/L (MIMIT).
    case lpg
    /// Metano/CNG — prezzo €/kg (MIMIT); `fuelConsumptionLPerKm` interpreta kg/km.
    case cng
    case unknown
}

extension Powertrain {
    /// Etichetta IT per picker (benzina/diesel/GPL/metano/ibrida).
    func catalogFuelLabel(fuelKind: FuelKind) -> String {
        switch self {
        case .ice:
            switch fuelKind {
            case .diesel: return L10n.powertrainDieselLabel
            case .petrol: return L10n.powertrainPetrolLabel
            case .lpg: return L10n.powertrainLpgLabel
            case .cng: return L10n.powertrainCngLabel
            case .unknown: return L10n.powertrainIceLabel
            }
        case .hev: return L10n.powertrainHevLabel
        case .phev: return L10n.powertrainPhevLabel
        case .ev: return L10n.powertrainEvLabel
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
    /// `petrol` / `diesel` se noto; `nil` → `resolvedFuelKind` euristica.
    let fuelKind: FuelKind?

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

    /// URL per l’immagine in UI (HTTPS). Scarta Unsplash source morto; host rischiosi filtrati in `VehicleHeroImage`.
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
    ///
    /// `share = clamp(autonomiaEV × 0.8 × giorniRicarica / kmAnnui, 0.1, 0.9)`.
    /// Con ricarica a casa si assume ricarica quasi quotidiana; senza, ~settimanale.
    func phevElectricKmShare(hasHomeCharging: Bool, yearlyKm: Double = 15_000) -> Double {
        guard powertrain == .phev else { return powertrain == .ev ? 1 : 0 }
        let electricRangeKm = Double(wltpRangeKm ?? 50)
        let chargeDays = hasHomeCharging ? 300.0 : 52.0
        let km = max(1.0, yearlyKm)
        let raw = electricRangeKm * 0.8 * chargeDays / km
        return min(0.9, max(0.1, raw))
    }

    /// Carburante effettivo per prezzi MIMIT e etichette picker.
    var resolvedFuelKind: FuelKind {
        if let fuelKind, fuelKind != .unknown { return fuelKind }
        switch powertrain {
        case .ev:
            return .unknown
        case .phev, .ice, .hev:
            return Self.inferFuelKind(brand: brand, model: model, year: year, trim: trim)
        }
    }

    var catalogFuelLabel: String {
        powertrain.catalogFuelLabel(fuelKind: resolvedFuelKind)
    }

    /// Nomi NHTSA / spazzatura da non mostrare nel picker.
    var isJunkCatalogEntry: Bool {
        let blob = "\(brand) \(model)".lowercased()
        let needles = [
            "radiator", "trailer", "manufacturing", " llc", " inc", " ltd",
            "company", "chassis", "incomplete", "motorhome", "cutaway",
        ]
        return needles.contains { blob.contains($0) }
    }

    private static let dieselLeanModels: Set<String> = [
        "ateca", "tiguan", "touareg", "qashqai", "x-trail", "sportage", "sorento",
        "tucson", "santa fe", "kuga", "mondeo", "passat", "superb", "octavia",
        "3008", "5008", "508", "c5 aircross", "kadjar", "koleos", "outlander",
        "asx", "rav4", "land cruiser", "discovery", "discovery sport",
        "range rover evoque", "range rover sport", "defender", "glc", "gle",
        "x3", "x5", "q5", "q7", "a4", "a6", "3 series", "5 series",
        "c-class", "e-class", "vito", "transporter",
    ]

    private static let petrolLeanModels: Set<String> = [
        "panda", "500", "500l", "500x", "punto", "twingo", "clio", "micra",
        "aygo", "yaris", "i10", "i20", "picanto", "rio", "up!", "polo",
        "corsa", "208", "108", "107", "c1", "c3", "ibiza", "fabia", "mii",
    ]

    private static func inferFuelKind(brand: String, model: String, year: Int, trim: String?) -> FuelKind {
        let blob = "\(model) \(trim ?? "")".lowercased()
        if blob.contains("gpl") || blob.contains("lpg") || blob.contains("eco-g") || blob.contains("eco g") {
            return .lpg
        }
        if blob.contains("metano") || blob.contains("cng") || blob.contains("natural power") {
            return .cng
        }
        if blob.contains("diesel") || blob.contains("tdi") || blob.contains("tdci")
            || blob.contains(" dci") || blob.contains("hdi") || blob.contains("jtd")
            || blob.contains("crd") || blob.contains("skyactiv-d") || blob.contains("bluehdi") {
            return .diesel
        }
        if blob.contains("benzina") || blob.contains("petrol") || blob.contains("tsi")
            || blob.contains("tfsi") || blob.contains("tce") || blob.contains("mpi")
            || blob.contains("gdi") || blob.contains("skyactiv-g") {
            return .petrol
        }
        let key = model.lowercased()
        if petrolLeanModels.contains(key) { return .petrol }
        // SUV / family diesel-leaning in IT roughly 2010–2021.
        if dieselLeanModels.contains(key), (2010...2021).contains(year) {
            return .diesel
        }
        if dieselLeanModels.contains(key), year >= 2022 {
            // Post-2022 mix più benzina/ibrido: default benzina se non specificato.
            return .petrol
        }
        return .petrol
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
        confidenceScore: Double? = nil,
        fuelKind: FuelKind? = nil
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
        self.fuelKind = fuelKind
    }
}

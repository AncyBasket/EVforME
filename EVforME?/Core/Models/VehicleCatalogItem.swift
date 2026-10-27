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
    /// Potenza kW da EEA (`ep__KW_`, spesso picco). Solo informativa — il bollo EV usa P.2 a libretto dall’utente.
    let powerKw: Double?
    /// `true` se `energyConsumptionKWhPerKm` / WLTP kWh è il valore **ponderato** (non solo elettrico).
    let energyIsWeighted: Bool?
    /// `true` se mancano CS fuel e/o kWh charge-depleting usabili nei calcoli — niente verdetto senza override utente.
    let catalogDataIncomplete: Bool?
    /// Campi ancora mancanti per il calcolo (es. `energyConsumptionKWhPerKm`). Vuoto ⇒ completo.
    let missingCalcFields: [String]?
    /// Provenienza per campo ufficiale salvato (dominio anno URL).
    let fieldSources: [String: String]?
    /// Consumo carburante WLTP **ponderato** (solo informativo; mai nei calcoli).
    let weightedFuelConsumptionLPerKm: Double?
    /// Consumo elettrico WLTP **ponderato** (solo informativo; mai nei calcoli).
    let weightedEnergyConsumptionKWhPerKm: Double?
    /// Riga versione EEA: punta alla riga modello/anno genitore.
    let parentId: String?
    /// Autonomia WLTP massima del gruppo versione (min è `wltpRangeKm`, caso prudente).
    let wltpRangeKmMax: Int?
    /// Consumo minimo del gruppo (kWh/km); il catalogo usa `energyConsumptionKWhPerKm` = max (prudente).
    let energyConsumptionKWhPerKmMin: Double?
    /// Testo autonomia min–max (cerchi/optional), solo versioni EEA raggruppate.
    let variantRangeCaption: String?
    /// `true` se autonomia/consumo in catalogo sono il bound prudente (min Zr / max Wh).
    let usesPrudentVariantBounds: Bool?
    /// `true` se il titolo versione è un allestimento ufficiale OEM (nome · kW).
    let officialMatched: Bool?
    /// Nota piccola per versioni non matchate (potenza omologata EEA ≠ potenza max).
    let eeaHomologationNote: String?

    var displayName: String {
        if let trim, !trim.isEmpty {
            return "\(brand) \(model) \(trim) (\(year))"
        }
        return "\(brand) \(model) (\(year))"
    }

    /// True se questa riga è una versione EEA figlia.
    var isEEAVariantChild: Bool {
        guard let parentId, !parentId.isEmpty else { return false }
        return true
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
        if let caption = variantRangeCaption, !caption.isEmpty {
            parts.append(caption)
        } else if let wltpRangeKm {
            if let wltpRangeKmMax, wltpRangeKmMax != wltpRangeKm {
                parts.append("\(wltpRangeKm)–\(wltpRangeKmMax) km")
            } else {
                parts.append("\(wltpRangeKm) km")
            }
        }
        if let note = eeaHomologationNote, !note.isEmpty {
            parts.append(note)
        } else if officialMatched == true, let powerKw, powerKw > 0 {
            parts.append(String(format: "%.0f kW", powerKw))
        } else if officialMatched != false, let powerKw, powerKw > 0, parentId == nil {
            parts.append(String(format: "%.0f kW", powerKw))
        }
        if let energy = resolvedEnergyKWhPerKm {
            parts.append(String(format: "%.1f kWh/100", energy * 100.0))
        }
        if usesPrudentVariantBounds == true {
            parts.append(L10n.variantPrudentCalcNote)
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

    /// Energia catalogo dichiarata come WLTP ponderato (non charge-depleting / solo elettrico).
    var usesWeightedElectricEnergy: Bool { energyIsWeighted == true }

    /// Dati catalogo insufficienti per un verdetto automatico (PHEV senza CS+CD, BEV senza kWh).
    var hasIncompleteCatalogData: Bool { catalogDataIncomplete == true }

    /// Campi di calcolo ancora assenti (da `missingCalcFields` o euristica sui valori usabili).
    var resolvedMissingCalcFields: [String] {
        if let missingCalcFields { return missingCalcFields }
        var miss: [String] = []
        if usableChargeSustainingFuelLPerKm == nil, powertrain == .phev || powertrain == .ice || powertrain == .hev {
            miss.append("fuelConsumptionLPerKm")
        }
        if usableChargeDepletingEnergyKWhPerKm == nil, powertrain == .phev || powertrain == .ev {
            miss.append("energyConsumptionKWhPerKm")
        }
        if powertrain == .phev {
            if wltpRangeKm == nil { miss.append("wltpRangeKm") }
            if batteryKWh == nil { miss.append("batteryKWh") }
        }
        return miss
    }

    /// Fonte ufficiale per un campo catalogo, se presente.
    func fieldSource(for key: String) -> String? {
        guard let fieldSources, let s = fieldSources[key], !s.isEmpty else { return nil }
        return s
    }

    /// Fonte consumi EPA USA (ciclo diverso dal WLTP) — mostrare nota esplicita in UI.
    var usesEPACatalogSource: Bool {
        if (market ?? "").uppercased() == "US/EPA" { return true }
        return HowWeCalculateExplainer.looksLikeEPASource(sourceName ?? "")
    }

    /// Consumo benzina charge-sustaining usabile nei calcoli (≥ 3 L/100, non ponderato).
    var usableChargeSustainingFuelLPerKm: Double? {
        guard let fuel = fuelConsumptionLPerKm, fuel > 0 else { return nil }
        if powertrain == .phev, fuel * 100.0 < 3.0 { return nil }
        return fuel
    }

    /// Consumo elettrico charge-depleting usabile nei calcoli (non ponderato).
    var usableChargeDepletingEnergyKWhPerKm: Double? {
        if usesWeightedElectricEnergy { return nil }
        return resolvedEnergyKWhPerKm
    }

    /// Quota km elettrici stimata per PHEV (0…1).
    ///
    /// `share = clamp(autonomiaEV × 0.8 × giorniRicarica / kmAnnui, 0.1, 0.6)`.
    /// Tetto 0,6 senza dati utente (ICCT). Con ricarica a casa ≈ quotidiana; senza, ~settimanale.
    func phevElectricKmShare(hasHomeCharging: Bool, yearlyKm: Double = 15_000) -> Double {
        guard powertrain == .phev else { return powertrain == .ev ? 1 : 0 }
        let electricRangeKm = Double(wltpRangeKm ?? 50)
        let chargeDays = hasHomeCharging ? 300.0 : 52.0
        let km = max(1.0, yearlyKm)
        let raw = electricRangeKm * 0.8 * chargeDays / km
        return min(0.6, max(0.1, raw))
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

    /// Nomi NHTSA / spazzatura / modelli fantasma da non mostrare nel picker.
    var isJunkCatalogEntry: Bool {
        let blob = "\(brand) \(model)".lowercased()
        let needles = [
            "radiator", "trailer", "manufacturing", " llc", " inc", " ltd",
            "company", "chassis", "incomplete", "motorhome", "cutaway",
            "bradford", "affordable aluminum", "b-750", "axxess",
        ]
        if needles.contains(where: { blob.contains($0) }) { return true }
        // Dead EU passenger names that must not reappear as recent catalog years.
        let brandKey = brand.lowercased().replacingOccurrences(of: "-", with: " ")
        let modelKey = model.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if brandKey.contains("audi"), ["100", "200", "80", "90", "4000", "5000"].contains(modelKey), year >= 2000 {
            return true
        }
        if brandKey.contains("mercedes"),
           ["190", "200", "220", "230", "240", "250", "260", "280", "300", "380", "420", "500", "560", "600"].contains(modelKey),
           year >= 2010 {
            return true
        }
        if brandKey.contains("bmw"), ["228", "323i", "323"].contains(modelKey), year >= 2015 {
            return true
        }
        if brandKey.contains("kia"), modelKey == "miami" { return true }
        if brandKey.contains("nissan"), modelKey == "axxess" { return true }
        // 350Z left production ~2009 — later catalog years are ghosts.
        if brandKey.contains("nissan"), modelKey == "350z", year >= 2010 { return true }
        if brandKey.contains("peugeot"), modelKey == "405", year >= 2010 { return true }
        if brandKey.contains("hyundai"), ["genesis", "excel"].contains(modelKey), year >= 2015 {
            return true
        }
        return false
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
        fuelKind: FuelKind? = nil,
        powerKw: Double? = nil,
        energyIsWeighted: Bool? = nil,
        catalogDataIncomplete: Bool? = nil,
        missingCalcFields: [String]? = nil,
        fieldSources: [String: String]? = nil,
        weightedFuelConsumptionLPerKm: Double? = nil,
        weightedEnergyConsumptionKWhPerKm: Double? = nil,
        parentId: String? = nil,
        wltpRangeKmMax: Int? = nil,
        energyConsumptionKWhPerKmMin: Double? = nil,
        variantRangeCaption: String? = nil,
        usesPrudentVariantBounds: Bool? = nil,
        officialMatched: Bool? = nil,
        eeaHomologationNote: String? = nil
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
        self.powerKw = powerKw
        self.energyIsWeighted = energyIsWeighted
        self.catalogDataIncomplete = catalogDataIncomplete
        self.missingCalcFields = missingCalcFields
        self.fieldSources = fieldSources
        self.weightedFuelConsumptionLPerKm = weightedFuelConsumptionLPerKm
        self.weightedEnergyConsumptionKWhPerKm = weightedEnergyConsumptionKWhPerKm
        self.parentId = parentId
        self.wltpRangeKmMax = wltpRangeKmMax
        self.energyConsumptionKWhPerKmMin = energyConsumptionKWhPerKmMin
        self.variantRangeCaption = variantRangeCaption
        self.usesPrudentVariantBounds = usesPrudentVariantBounds
        self.officialMatched = officialMatched
        self.eeaHomologationNote = eeaHomologationNote
    }
}

//
//  HowWeCalculateExplainer.swift
//  EVforME?
//
//  Unica fonte di verità per i numeri mostrati in “Come calcoliamo”.
//  Nessun valore hardcodato in UI: tutto passa da qui / costanti di calcolo.
//

import Foundation

enum ConfidenceBand: Equatable {
    case high
    case medium
    case low
    case unknown

    /// Soglie allineate all’uso catalogo (≥0.8 alta, ≥0.5 media).
    static func from(score: Double?) -> ConfidenceBand {
        guard let score else { return .unknown }
        if score >= 0.8 { return .high }
        if score >= 0.5 { return .medium }
        return .low
    }

    var localizedTitle: String {
        switch self {
        case .high: return L10n.howWeCalculateConfidenceHigh
        case .medium: return L10n.howWeCalculateConfidenceMedium
        case .low: return L10n.howWeCalculateConfidenceLow
        case .unknown: return L10n.howWeCalculateConfidenceUnknown
        }
    }
}

struct HowWeCalculateVehicleBlock: Equatable {
    let roleTitle: String
    let displayName: String
    let sourceLabel: String?
    let sourceURL: URL?
    let confidence: ConfidenceBand
    let showsWeightedEnergyNote: Bool
    let showsCO2ToFuelNote: Bool
    let fuelKindForCO2: FuelKind
}

struct HowWeCalculateBolloBlock: Equatable {
    let regionTitle: String
    let evEURPerKw: Double?
    let usesNationalEVEstimate: Bool
    let evExemptionYears: Int
    let permanentlyExempt: Bool
    let superbolloThresholdKw: Double
    let superbolloEURPerKwAbove: Double
    let nationalEVBolloEURPerKw: Double
    let petrolCO2PerL100: Double
    let dieselCO2PerL100: Double
}

struct HowWeCalculateModel: Equatable {
    let source: HowWeCalculateVehicleBlock?
    let target: HowWeCalculateVehicleBlock?
    let bollo: HowWeCalculateBolloBlock
    let eurLexURL: URL
    let fuelPriceSourceKey: String
    let electricityPriceSourceKey: String
}

enum HowWeCalculateExplainer {
    /// Soglia e tariffa superbollo — devono coincidere con `ItalianRegion.nationalSuperbolloEUR`.
    static let superbolloThresholdKw: Double = 185
    static let superbolloEURPerKwAboveThreshold: Double = 20

    static func confidenceBand(for score: Double?) -> ConfidenceBand {
        ConfidenceBand.from(score: score)
    }

    /// Tariffa EV €/kW usata dal calcolo (stesso getter del bollo).
    static func evBolloEURPerKw(for region: ItalianRegion) -> Double? {
        region.evBolloEURPerKw
    }

    /// Stima nazionale quando non c’è tariffa regionale dedicata (unspecified) oppure otherUnknown (nil).
    static func usesNationalEVBolloEstimate(for region: ItalianRegion) -> Bool {
        switch region {
        case .unspecified:
            return true
        case .otherUnknown:
            return false
        case .basilicata, .puglia, .umbria, .valleDAosta, .sicilia:
            // Stesso €/kW della stima nazionale in codice.
            return abs((region.evBolloEURPerKw ?? -1) - OwnershipCostEstimates.nationalEVBolloEURPerKw) < 1e-9
        default:
            return false
        }
    }

    static func sourceURL(from sourceName: String?) -> URL? {
        guard let sourceName else { return nil }
        guard let range = sourceName.range(of: "https://") ?? sourceName.range(of: "http://") else {
            return nil
        }
        let fromHttp = sourceName[range.lowerBound...]
        let token = fromHttp.split(whereSeparator: { $0.isWhitespace || $0 == "—" || $0 == "|" }).first.map(String.init) ?? String(fromHttp)
        let cleaned = token.trimmingCharacters(in: CharacterSet(charactersIn: ".,);]}"))
        return URL(string: cleaned)
    }

    /// Heuristica: il consumo L/km deriva da CO₂ se la fonte lo dichiara (EEA CO2→FC / Reg. 2017/1151).
    static func fuelLikelyFromCO2(sourceName: String?) -> Bool {
        let s = (sourceName ?? "").lowercased()
        return s.contains("co2")
            || s.contains("2017/1151")
            || s.contains("co2→")
            || s.contains("co2->")
            || s.contains("eea") && (s.contains("wltp") || s.contains("fc"))
    }

    static func makeModel(
        userInput: UserInput,
        catalog: VehicleCatalogService = .shared
    ) -> HowWeCalculateModel {
        let region = userInput.italianRegion
        let source = catalog.vehicle(by: userInput.sourceVehicleId).map {
            vehicleBlock(role: L10n.howWeCalculateRoleSource, vehicle: $0)
        }
        let target = catalog.vehicle(by: userInput.targetVehicleId).map {
            vehicleBlock(role: L10n.howWeCalculateRoleTarget, vehicle: $0)
        }
        let exemption: Int = {
            if region.evPermanentlyExempt { return region.evExemptionYears }
            let year = catalog.vehicle(by: userInput.targetVehicleId)?.year
                ?? catalog.vehicle(by: userInput.sourceVehicleId)?.year
                ?? Calendar.current.component(.year, from: Date())
            return region.evExemptionYears(forVehicleYear: year)
        }()

        let bollo = HowWeCalculateBolloBlock(
            regionTitle: region.title,
            evEURPerKw: evBolloEURPerKw(for: region),
            usesNationalEVEstimate: usesNationalEVBolloEstimate(for: region),
            evExemptionYears: exemption,
            permanentlyExempt: region.evPermanentlyExempt,
            superbolloThresholdKw: superbolloThresholdKw,
            superbolloEURPerKwAbove: superbolloEURPerKwAboveThreshold,
            nationalEVBolloEURPerKw: OwnershipCostEstimates.nationalEVBolloEURPerKw,
            petrolCO2PerL100: FuelFromCO2Constants.petrolCO2PerL100,
            dieselCO2PerL100: FuelFromCO2Constants.dieselCO2PerL100
        )

        return HowWeCalculateModel(
            source: source,
            target: target,
            bollo: bollo,
            eurLexURL: FuelFromCO2Constants.eurLexRegulationURL,
            fuelPriceSourceKey: "mimit",
            electricityPriceSourceKey: "eurostat"
        )
    }

    private static func vehicleBlock(role: String, vehicle: VehicleCatalogItem) -> HowWeCalculateVehicleBlock {
        HowWeCalculateVehicleBlock(
            roleTitle: role,
            displayName: vehicle.displayName,
            sourceLabel: vehicle.sourceName,
            sourceURL: sourceURL(from: vehicle.sourceName),
            confidence: confidenceBand(for: vehicle.confidenceScore),
            showsWeightedEnergyNote: vehicle.usesWeightedElectricEnergy,
            showsCO2ToFuelNote: fuelLikelyFromCO2(sourceName: vehicle.sourceName),
            fuelKindForCO2: vehicle.resolvedFuelKind
        )
    }
}

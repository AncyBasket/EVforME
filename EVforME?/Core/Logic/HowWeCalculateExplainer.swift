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

/// Categoria fonte consumi (localizzata), ricavata da `sourceName`.
enum ConsumptionSourceCategory: Equatable {
    case eeaWLTP
    case epaUSA
    case manufacturer
    case estimate
    case unknown

    var localizedTitle: String {
        switch self {
        case .eeaWLTP: return L10n.howWeCalculateSourceCategoryEEA
        case .epaUSA: return L10n.howWeCalculateSourceCategoryEPA
        case .manufacturer: return L10n.howWeCalculateSourceCategoryManufacturer
        case .estimate: return L10n.howWeCalculateSourceCategoryEstimate
        case .unknown: return L10n.howWeCalculateSourceCategoryUnknown
        }
    }

    /// Link di default quando `sourceName` non contiene già un URL.
    var defaultURL: URL? {
        switch self {
        case .eeaWLTP: return OfficialLinks.eeaCO2CarsDataset
        case .epaUSA: return OfficialLinks.epaFuelEconomy
        case .manufacturer, .estimate, .unknown: return nil
        }
    }
}

/// Percorso bollo allineato a `OwnershipCostEstimates.bolloPerYearDetail`.
enum HowWeCalculateBolloPath: Equatable {
    case evPermanentExempt
    case evInExemption(years: Int)
    case evQuarterRate(rateEURPerKw: Double, exemptionYears: Int, usesNationalEstimate: Bool)
    case evNotEstimated
    case thermalRegional(showsSuperbollo: Bool)
    case thermalCatalogEstimate
    case thermalUnknown
}

struct HowWeCalculateVehicleBlock: Equatable {
    let roleTitle: String
    let displayName: String
    let powertrain: Powertrain
    let sourceCategory: ConsumptionSourceCategory
    let sourceURL: URL?
    let confidence: ConfidenceBand
    let showsWeightedEnergyNote: Bool
    let showsCO2ToFuelNote: Bool
    let fuelKindForCO2: FuelKind
    let bolloPath: HowWeCalculateBolloPath
    /// Media annua sull’orizzonte — stesso valore di `OperatingCostBreakdown.taxes` nel simulatore.
    let bolloAverageEUR: Double
    /// Bollo del solo anno di riferimento (`bolloPerYearDetail`).
    let bolloThisYearEUR: Double
    let bolloIsKnown: Bool
}

struct HowWeCalculateBolloShared: Equatable {
    let regionTitle: String
    let nationalEVBolloEURPerKw: Double
    let petrolCO2PerL100: Double
    let dieselCO2PerL100: Double
    let superbolloThresholdKw: Double
    let superbolloEURPerKwAbove: Double
}

struct HowWeCalculateModel: Equatable {
    let source: HowWeCalculateVehicleBlock?
    let target: HowWeCalculateVehicleBlock?
    let bolloShared: HowWeCalculateBolloShared
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
            return abs((region.evBolloEURPerKw ?? -1) - OwnershipCostEstimates.nationalEVBolloEURPerKw) < 1e-9
        default:
            return false
        }
    }

    /// Formatta €/kW con la locale corrente (virgola in IT, punto in EN).
    static func formatEURPerKw(_ value: Double) -> String {
        let nf = NumberFormatter()
        nf.locale = .autoupdatingCurrent
        nf.numberStyle = .decimal
        nf.minimumFractionDigits = 2
        nf.maximumFractionDigits = 2
        return nf.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
    }

    static func formatEURAmount(_ value: Double) -> String {
        let nf = NumberFormatter()
        nf.locale = .autoupdatingCurrent
        nf.numberStyle = .decimal
        nf.minimumFractionDigits = 0
        nf.maximumFractionDigits = 2
        return nf.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
    }

    /// EPA solo come token (`EPA-FuelEconomy`, `epa` non attaccato a lettere) o `fueleconomy`.
    static func looksLikeEPASource(_ sourceName: String) -> Bool {
        let s = sourceName.lowercased()
        if s.contains("fueleconomy") { return true }
        // `(?<![a-z0-9])epa(?![a-z0-9])` — evita match in "grandepanda".
        return s.range(of: #"(?<![a-z0-9])epa(?![a-z0-9])"#, options: .regularExpression) != nil
    }

    static func consumptionSourceCategory(from sourceName: String?) -> ConsumptionSourceCategory {
        let s = (sourceName ?? "").lowercased()
        guard !s.isEmpty else { return .unknown }
        if looksLikeEPASource(sourceName ?? "") {
            return .epaUSA
        }
        if s.contains("stima") {
            return .estimate
        }
        if s.contains("eea") || s.contains("co2cars") {
            return .eeaWLTP
        }
        if s.contains("listino")
            || s.contains("scheda")
            || s.contains("costruttore")
            || s.contains("manufacturer")
            || s.contains("press")
            || s.contains("newsroom")
            || s.contains("preisliste")
            || s.contains("import-")
            || s.contains("https://")
            || s.contains("http://") {
            return .manufacturer
        }
        if s.contains("common-") {
            return .estimate
        }
        return .unknown
    }

    /// URL esplicito in `sourceName`, altrimenti link di default della categoria (EEA/EPA).
    static func sourceURL(from sourceName: String?, category: ConsumptionSourceCategory? = nil) -> URL? {
        if let embedded = embeddedURL(in: sourceName) {
            return embedded
        }
        let cat = category ?? consumptionSourceCategory(from: sourceName)
        return cat.defaultURL
    }

    static func embeddedURL(in sourceName: String?) -> URL? {
        guard let sourceName else { return nil }
        guard let range = sourceName.range(of: "https://") ?? sourceName.range(of: "http://") else {
            return nil
        }
        let fromHttp = sourceName[range.lowerBound...]
        let token = fromHttp.split(whereSeparator: { $0.isWhitespace || $0 == "—" || $0 == "|" }).first.map(String.init) ?? String(fromHttp)
        let cleaned = token.trimmingCharacters(in: CharacterSet(charactersIn: ".,);]}"))
        return URL(string: cleaned)
    }

    /// Heuristica: L/100 da CO₂ solo per auto con carburante (ICE/HEV/PHEV), mai BEV.
    static func fuelLikelyFromCO2(sourceName: String?, powertrain: Powertrain) -> Bool {
        guard powertrain != .ev else { return false }
        let s = (sourceName ?? "").lowercased()
        return s.contains("co2")
            || s.contains("2017/1151")
            || s.contains("co2→")
            || s.contains("co2->")
            || (s.contains("eea") && (s.contains("wltp") || s.contains("fc") || s.contains("co2cars")))
    }

    static func makeModel(
        userInput: UserInput,
        catalog: VehicleCatalogService = .shared,
        referenceYear: Int = Defaults.referenceCalendarYear
    ) -> HowWeCalculateModel {
        let region = userInput.italianRegion
        let years = max(1, userInput.ownershipYears)
        let source = catalog.vehicle(by: userInput.sourceVehicleId).map {
            vehicleBlock(
                role: L10n.howWeCalculateRoleSource,
                vehicle: $0,
                bookletKw: userInput.sourceBookletPowerKwP2,
                region: region,
                referenceYear: referenceYear,
                ownershipYears: years
            )
        }
        let target = catalog.vehicle(by: userInput.targetVehicleId).map {
            vehicleBlock(
                role: L10n.howWeCalculateRoleTarget,
                vehicle: $0,
                bookletKw: userInput.targetBookletPowerKwP2,
                region: region,
                referenceYear: referenceYear,
                ownershipYears: years
            )
        }

        let shared = HowWeCalculateBolloShared(
            regionTitle: region.title,
            nationalEVBolloEURPerKw: OwnershipCostEstimates.nationalEVBolloEURPerKw,
            petrolCO2PerL100: FuelFromCO2Constants.petrolCO2PerL100,
            dieselCO2PerL100: FuelFromCO2Constants.dieselCO2PerL100,
            superbolloThresholdKw: superbolloThresholdKw,
            superbolloEURPerKwAbove: superbolloEURPerKwAboveThreshold
        )

        return HowWeCalculateModel(
            source: source,
            target: target,
            bolloShared: shared,
            eurLexURL: FuelFromCO2Constants.eurLexRegulationURL,
            fuelPriceSourceKey: "mimit",
            electricityPriceSourceKey: "eurostat"
        )
    }

    /// Stesso media/isKnown del verdetto (`bolloTotalOverHorizon` / anni) + dettaglio anno corrente.
    static func bolloDetail(
        vehicle: VehicleCatalogItem,
        bookletKw: Double?,
        region: ItalianRegion,
        referenceYear: Int = Defaults.referenceCalendarYear,
        ownershipYears: Int
    ) -> (
        path: HowWeCalculateBolloPath,
        averageEUR: Double,
        thisYearEUR: Double,
        isKnown: Bool
    ) {
        // Allineato a `EVSimulator.simulate`: EV non usano `catalogPowerKw` (solo P.2).
        let catalogKw: Double? = vehicle.powertrain == .ev ? nil : vehicle.powerKw
        let years = max(1, ownershipYears)
        let thisYear = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: vehicle.taxesPerYear,
            powertrain: vehicle.powertrain,
            vehicleYear: vehicle.year,
            referenceYear: referenceYear,
            bookletPowerKwP2: bookletKw,
            italianRegion: region,
            fuelKind: vehicle.resolvedFuelKind,
            catalogPowerKw: catalogKw
        )
        let horizon = OwnershipCostEstimates.bolloTotalOverHorizon(
            catalogTaxesPerYear: vehicle.taxesPerYear,
            powertrain: vehicle.powertrain,
            vehicleYear: vehicle.year,
            referenceYear: referenceYear,
            ownershipYears: years,
            bookletPowerKwP2: bookletKw,
            italianRegion: region,
            fuelKind: vehicle.resolvedFuelKind,
            catalogPowerKw: catalogKw
        )
        let path = bolloPath(
            vehicle: vehicle,
            bookletKw: bookletKw,
            region: region,
            referenceYear: referenceYear,
            estimate: thisYear
        )
        return (
            path,
            horizon.amount / Double(years),
            thisYear.amount,
            horizon.isKnown
        )
    }

    private static func vehicleBlock(
        role: String,
        vehicle: VehicleCatalogItem,
        bookletKw: Double?,
        region: ItalianRegion,
        referenceYear: Int,
        ownershipYears: Int
    ) -> HowWeCalculateVehicleBlock {
        let category = consumptionSourceCategory(from: vehicle.sourceName)
        let detail = bolloDetail(
            vehicle: vehicle,
            bookletKw: bookletKw,
            region: region,
            referenceYear: referenceYear,
            ownershipYears: ownershipYears
        )
        return HowWeCalculateVehicleBlock(
            roleTitle: role,
            displayName: vehicle.displayName,
            powertrain: vehicle.powertrain,
            sourceCategory: category,
            sourceURL: sourceURL(from: vehicle.sourceName, category: category),
            confidence: confidenceBand(for: vehicle.confidenceScore),
            showsWeightedEnergyNote: vehicle.usesWeightedElectricEnergy,
            showsCO2ToFuelNote: fuelLikelyFromCO2(sourceName: vehicle.sourceName, powertrain: vehicle.powertrain),
            fuelKindForCO2: vehicle.resolvedFuelKind,
            bolloPath: detail.path,
            bolloAverageEUR: detail.averageEUR,
            bolloThisYearEUR: detail.thisYearEUR,
            bolloIsKnown: detail.isKnown
        )
    }

    private static func bolloPath(
        vehicle: VehicleCatalogItem,
        bookletKw: Double?,
        region: ItalianRegion,
        referenceYear: Int,
        estimate: OwnershipCostEstimates.BolloEstimate
    ) -> HowWeCalculateBolloPath {
        _ = estimate
        switch vehicle.powertrain {
        case .ev:
            if region.evPermanentlyExempt {
                return .evPermanentExempt
            }
            let exemptYears = region.evExemptionYears(forVehicleYear: vehicle.year)
            let age = max(0, referenceYear - vehicle.year)
            if age < exemptYears {
                return .evInExemption(years: exemptYears)
            }
            guard let rate = region.evBolloEURPerKw else {
                return .evNotEstimated
            }
            let kw = bookletKw
            guard let kw, kw > 0 else {
                return .evNotEstimated
            }
            _ = kw
            return .evQuarterRate(
                rateEURPerKw: rate,
                exemptionYears: exemptYears,
                usesNationalEstimate: usesNationalEVBolloEstimate(for: region)
            )
        case .phev, .hev, .ice:
            let kw = bookletKw ?? vehicle.powerKw
            if let kw, kw > 0,
               region.thermalBolloEUR(
                powerKw: kw,
                fuelKind: vehicle.resolvedFuelKind,
                vehicleYear: vehicle.year,
                referenceYear: referenceYear
               ) != nil {
                let superbollo = ItalianRegion.nationalSuperbolloEUR(
                    powerKw: kw,
                    vehicleYear: vehicle.year,
                    referenceYear: referenceYear
                )
                return .thermalRegional(showsSuperbollo: superbollo > 0)
            }
            if vehicle.taxesPerYear > 0 {
                return .thermalCatalogEstimate
            }
            return .thermalUnknown
        }
    }
}

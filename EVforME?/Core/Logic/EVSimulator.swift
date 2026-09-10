//
//  EVSimulator.swift
//  EVforME?
//

import Foundation

struct EVSimulationInput {
    let yearlyKm: Double
    let years: Int
    let fuelPricePerLiter: Double
    let electricityPricePerKWh: Double
    var areaType: AreaType = .mixed
    var tripProfile: TripProfile = .custom
    var hasHomeCharging: Bool = true
    var sourcePurchasePrice: Double = 12_000
    var targetPurchasePrice: Double = 32_000
    /// L/km override (già convertito da L/100 km).
    var iceFuelLPerKmOverride: Double? = nil
    /// kWh/km override (già convertito da kWh/100 km).
    var evKWhPerKmOverride: Double? = nil
    /// Configurazione ricarica personalizzata
    var chargingConfiguration: ChargingConfiguration = ChargingConfiguration()
}

struct EVSimulationResult {
    let iceTotalCost: Double
    let evTotalCost: Double
    let totalSavings: Double
    let yearlyIceCost: Double
    let yearlyEvCost: Double
    let sourceBreakdown: OperatingCostBreakdown
    let targetBreakdown: OperatingCostBreakdown
}

/// Costo operativo annuo spezzato (stessa base del verdetto).
struct OperatingCostBreakdown: Equatable {
    let energy: Double
    let maintenance: Double
    let taxes: Double
    let insurance: Double

    var total: Double { energy + maintenance + taxes + insurance }
}

enum OwnershipCostEstimates {
    /// Assicurazione annua migliorata con fascie di prezzo più granulari e fattori aggiuntivi
    static func insurancePerYear(purchasePrice: Double, yearlyKm: Double, electrified: Bool) -> Double {
        // Fascie di prezzo per tassi base più accurati
        let priceTierRate: Double
        switch purchasePrice {
        case 0..<15_000:
            priceTierRate = electrified ? 0.028 : 0.026
        case 15_000..<25_000:
            priceTierRate = electrified ? 0.030 : 0.028
        case 25_000..<40_000:
            priceTierRate = electrified ? 0.032 : 0.030
        case 40_000..<60_000:
            priceTierRate = electrified ? 0.035 : 0.033
        case 60_000..<80_000:
            priceTierRate = electrified ? 0.038 : 0.036
        default:
            priceTierRate = electrified ? 0.042 : 0.040
        }
        
        // Fattore chilometraggio con progressione non lineare
        let kmFactor: Double
        switch yearlyKm {
        case 0..<5_000:
            kmFactor = electrified ? 0.006 : 0.008
        case 5_000..<15_000:
            kmFactor = electrified ? 0.008 : 0.010
        case 15_000..<25_000:
            kmFactor = electrified ? 0.010 : 0.012
        case 25_000..<40_000:
            kmFactor = electrified ? 0.012 : 0.014
        default:
            kmFactor = electrified ? 0.014 : 0.016
        }
        
        // Calcolo base
        let fromPrice = purchasePrice * priceTierRate
        let fromKm = yearlyKm * kmFactor
        
        // Minimum base insurance (franchigia minima)
        let minimumBase: Double = electrified ? 380 : 320
        
        // Fattore sicurezza extra per veicoli premium
        let premiumFactor = purchasePrice > 50_000 ? 1.15 : 1.0
        
        return max(minimumBase, (fromPrice * 0.70 + fromKm) * premiumFactor)
    }

    /// Residuo stimato migliorato con deprezzamento non lineare
    static func residualValue(purchasePrice: Double, years: Int, electrified: Bool) -> Double {
        // Tassi di deprezzamento annuali più realistici
        let annualDepreciation: Double
        let yearsDbl = Double(max(1, years))
        
        if electrified {
            // EV deprezzamento più rapido nei primi anni, poi stabilizza
            if yearsDbl <= 2 {
                annualDepreciation = 0.18
            } else if yearsDbl <= 4 {
                annualDepreciation = 0.14
            } else {
                annualDepreciation = 0.12
            }
        } else {
            // ICE deprezzamento più lineare
            if yearsDbl <= 3 {
                annualDepreciation = 0.12
            } else {
                annualDepreciation = 0.10
            }
        }
        
        // Fattore aggiustamento per veicoli premium (miglior valore residuo → residuo più alto).
        let premiumAdjustment = purchasePrice > 40_000 ? 1.08 : 1.0
        
        let factor = pow(1.0 - annualDepreciation, yearsDbl) * premiumAdjustment
        return max(0, purchasePrice * factor)
    }
    
    /// Costi manutenzione migliorati con fasce di età veicolo
    static func maintenancePerYear(purchasePrice: Double, vehicleAge: Int, electrified: Bool) -> Double {
        let baseMaintenance: Double
        let ageMultiplier: Double
        
        // Base maintenance per fascia prezzo
        switch purchasePrice {
        case 0..<20_000:
            baseMaintenance = electrified ? 350 : 550
        case 20_000..<35_000:
            baseMaintenance = electrified ? 450 : 700
        case 35_000..<50_000:
            baseMaintenance = electrified ? 550 : 850
        default:
            baseMaintenance = electrified ? 700 : 1000
        }
        
        // Aumento manutenzione con età veicolo
        switch vehicleAge {
        case 0..<3:
            ageMultiplier = 0.8
        case 3..<6:
            ageMultiplier = 1.0
        case 6..<10:
            ageMultiplier = 1.3
        default:
            ageMultiplier = 1.6
        }
        
        return baseMaintenance * ageMultiplier
    }
}

final class EVSimulator {
    // MARK: - Simulazione
    func simulate(
        input: EVSimulationInput,
        scenario: Scenario,
        sourceVehicle: VehicleCatalogItem,
        targetVehicle: VehicleCatalogItem
    ) -> EVSimulationResult {

        let yearlyKm = input.yearlyKm
        let years = input.years

        let sourceEnergy = energyCostPerYear(
            vehicle: sourceVehicle,
            input: input,
            scenario: scenario,
            fuelOverrideLPerKm: input.iceFuelLPerKmOverride,
            energyOverrideKWhPerKm: nil,
            asSource: true
        )
        let targetEnergy = energyCostPerYear(
            vehicle: targetVehicle,
            input: input,
            scenario: scenario,
            fuelOverrideLPerKm: nil,
            energyOverrideKWhPerKm: input.evKWhPerKmOverride,
            asSource: false
        )

        let sourceInsurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: input.sourcePurchasePrice,
            yearlyKm: yearlyKm,
            electrified: sourceVehicle.powertrain != .ice
        )
        let targetInsurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: input.targetPurchasePrice,
            yearlyKm: yearlyKm,
            electrified: true
        )

        let currentYear = Calendar.current.component(.year, from: Date())
        let sourceMaintenance = OwnershipCostEstimates.maintenancePerYear(
            purchasePrice: input.sourcePurchasePrice,
            vehicleAge: max(0, currentYear - sourceVehicle.year),
            electrified: sourceVehicle.powertrain != .ice
        ) * scenario.iceCostMultiplier
        let targetMaintenance = OwnershipCostEstimates.maintenancePerYear(
            purchasePrice: input.targetPurchasePrice,
            vehicleAge: max(0, currentYear - targetVehicle.year),
            electrified: true
        ) * scenario.evCostMultiplier

        let sourceBreakdown = OperatingCostBreakdown(
            energy: sourceEnergy,
            maintenance: sourceMaintenance,
            taxes: sourceVehicle.taxesPerYear,
            insurance: sourceInsurance
        )
        let targetBreakdown = OperatingCostBreakdown(
            energy: targetEnergy,
            maintenance: targetMaintenance,
            taxes: targetVehicle.taxesPerYear,
            insurance: targetInsurance
        )

        let yearlyIceCost = sourceBreakdown.total
        let yearlyEvCost = targetBreakdown.total

        // Totali usati dal VerdictEngine = opex × anni (acquisto/residuo restano nel break-even).
        let iceTotalCost = yearlyIceCost * Double(years)
        let evTotalCost = yearlyEvCost * Double(years)
        let totalSavings = iceTotalCost - evTotalCost

        return EVSimulationResult(
            iceTotalCost: iceTotalCost,
            evTotalCost: evTotalCost,
            totalSavings: totalSavings,
            yearlyIceCost: yearlyIceCost,
            yearlyEvCost: yearlyEvCost,
            sourceBreakdown: sourceBreakdown,
            targetBreakdown: targetBreakdown
        )
    }

    private func energyCostPerYear(
        vehicle: VehicleCatalogItem,
        input: EVSimulationInput,
        scenario: Scenario,
        fuelOverrideLPerKm: Double?,
        energyOverrideKWhPerKm: Double?,
        asSource: Bool
    ) -> Double {
        let yearlyKm = input.yearlyKm
        let area = input.areaType
        let trip = input.tripProfile
        let fuelMult = asSource ? scenario.iceCostMultiplier : scenario.evCostMultiplier
        let elecMult = asSource ? scenario.iceCostMultiplier : scenario.evCostMultiplier

        switch vehicle.powertrain {
        case .ice:
            guard let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm, lPerKm > 0 else {
                return 0
            }
            return yearlyKm
                * lPerKm
                * area.iceConsumptionMultiplier
                * trip.iceExtraMultiplier
                * input.fuelPricePerLiter
                * fuelMult

        case .ev:
            guard let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm, kWhPerKm > 0 else {
                return 0
            }
            let annual = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm,
                energyConsumptionKWhPerKm: kWhPerKm,
                chargingConfig: input.chargingConfiguration
            )
            return annual
                * area.evConsumptionMultiplier
                * trip.evExtraMultiplier
                * elecMult

        case .phev:
            let share = vehicle.phevElectricKmShare(hasHomeCharging: input.hasHomeCharging)
            guard let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm, lPerKm > 0 else {
                return 0
            }
            guard let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm, kWhPerKm > 0 else {
                return 0
            }
            let fuelPart = yearlyKm * (1.0 - share)
                * lPerKm
                * area.iceConsumptionMultiplier
                * trip.iceExtraMultiplier
                * input.fuelPricePerLiter
                * fuelMult
            let elecPart = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm * share,
                energyConsumptionKWhPerKm: kWhPerKm,
                chargingConfig: input.chargingConfiguration
            )
                * area.evConsumptionMultiplier
                * trip.evExtraMultiplier
                * elecMult
            return fuelPart + elecPart
        }
    }
    
    // MARK: - Adapter per compatibilità con codice esistente
    
    /// Simula e restituisce un esito solo se i dati sono sufficienti.
    /// In caso di input incompleto/incoerente restituisce `nil` (fail-closed: niente verdetto finto).
    static func simulate(input: UserInput, scenario: Scenario? = nil) -> SimulationResult? {
        AppLogger.shared.debug("Starting simulation for \(input.dailyKm) km/year", category: .simulation)
        
        let validationErrors = InputValidator.validate(input)
        guard validationErrors.isEmpty else {
            AppLogger.shared.warning("Simulation validation failed: \(validationErrors.joined(separator: ", "))", category: .validation)
            return nil
        }
        
        let catalog = VehicleCatalogService.shared
        guard let sourceVehicle = catalog.vehicle(by: input.sourceVehicleId),
              let targetVehicle = catalog.vehicle(by: input.targetVehicleId) else {
            AppLogger.shared.error("Failed to find vehicles for simulation", category: .simulation)
            return nil
        }

        let iceOverride = input.sourceConsumptionOverrideLPer100Km.map { $0 / 100.0 }
        let evOverride = input.targetEnergyOverrideKWhPer100Km.map { $0 / 100.0 }
        guard Self.hasUsableConsumption(
            vehicle: sourceVehicle,
            fuelOverrideLPerKm: iceOverride,
            energyOverrideKWhPerKm: nil
        ), Self.hasUsableConsumption(
            vehicle: targetVehicle,
            fuelOverrideLPerKm: nil,
            energyOverrideKWhPerKm: evOverride
        ) else {
            AppLogger.shared.warning("Missing consumption data for selected vehicles", category: .simulation)
            return nil
        }
        
        let simulator = EVSimulator()
        let simulationInput = EVSimulationInput(
            yearlyKm: Double(input.dailyKm),
            years: input.ownershipYears,
            fuelPricePerLiter: input.fuelPrice,
            electricityPricePerKWh: input.electricityPricePerKWh,
            areaType: input.areaType,
            tripProfile: input.tripProfile,
            hasHomeCharging: input.hasHomeCharging,
            sourcePurchasePrice: input.sourcePurchasePrice,
            targetPurchasePrice: input.targetPurchasePrice,
            iceFuelLPerKmOverride: iceOverride,
            evKWhPerKmOverride: evOverride,
            chargingConfiguration: input.resolvedChargingConfiguration()
        )
        
        let selectedScenario = scenario ?? input.scenario
        
        AppLogger.shared.info("Simulating: \(sourceVehicle.displayName) -> \(targetVehicle.displayName)", category: .simulation)
        
        let result = simulator.simulate(
            input: simulationInput,
            scenario: selectedScenario,
            sourceVehicle: sourceVehicle,
            targetVehicle: targetVehicle
        )
        
        let weeklyKm = Double(input.dailyKm) / 52.0
        let baseKmPerCharge = input.hasHomeCharging ? 300.0 : 250.0
        let kmPerCharge = baseKmPerCharge * input.areaType.kmPerChargeFactor * input.tripProfile.chargeSeverityFactor
        let weeklyCharges: Int
        switch targetVehicle.powertrain {
        case .ev:
            weeklyCharges = max(1, Int(ceil(weeklyKm / kmPerCharge)))
        case .phev:
            weeklyCharges = max(1, Int(ceil(weeklyKm * 0.55 / kmPerCharge)))
        case .ice:
            weeklyCharges = 0
        }
        
        let yearlySavings = result.yearlyIceCost - result.yearlyEvCost
        let savingsBandLow = Int(yearlySavings * 0.9)
        let savingsBandHigh = Int(yearlySavings * 1.1)
        let savingsRangeLower = min(savingsBandLow, savingsBandHigh)
        let savingsRangeUpper = max(savingsBandLow, savingsBandHigh)

        let purchasePremium = input.netPurchasePremiumEUR
        let breakEvenMonths: Int?
        if yearlySavings > 50, purchasePremium > 0 {
            breakEvenMonths = max(1, Int(ceil(purchasePremium / yearlySavings * 12.0)))
        } else if yearlySavings > 50, purchasePremium <= 0 {
            breakEvenMonths = 1
        } else {
            breakEvenMonths = nil
        }

        let verdict = VerdictEngine.evaluate(
            result: result,
            scenario: selectedScenario,
            netPurchasePremiumEUR: purchasePremium,
            ownershipYears: input.ownershipYears
        )
        
        AppLogger.shared.info("Simulation complete: verdict=\(verdict.rawValue), savings=\(String(format: "%.2f", yearlySavings))€/year", category: .simulation)
        
        var reasons = [
            L10n.switchingFromTo(sourceVehicle.displayName, targetVehicle.displayName),
            L10n.chargePerWeek(weeklyCharges),
            L10n.saveUpToPerYear(Int(yearlySavings)),
            input.hasHomeCharging
                ? L10n.homeChargingEasier
                : L10n.publicChargingManageable
        ]
        if targetVehicle.powertrain == .phev {
            reasons.append(L10n.phevBlendReason)
        }
        reasons.append(L10n.insuranceIncludedReason)
        if input.includeIncentives {
            reasons.append(L10n.incentivesIncludedReason(Int(input.estimatedPurchaseIncentiveEUR)))
        }
        if input.sourceConsumptionOverrideLPer100Km != nil || input.targetEnergyOverrideKWhPer100Km != nil {
            reasons.append(L10n.stickerOverrideAppliedReason)
        }
        if let breakEvenMonths {
            reasons.append(L10n.breakEvenMonthsReason(breakEvenMonths))
        } else {
            reasons.append(L10n.breakEvenNotReachedReason)
        }
        
        var fears: [FearRealityItem] = []
        if weeklyCharges > 2 {
            fears.append(FearRealityItem(
                fear: L10n.fearRunOutBattery,
                reality: L10n.realityChargingFewTimes
            ))
        }
        if !input.hasHomeCharging {
            fears.append(FearRealityItem(
                fear: L10n.fearChargingComplicated,
                reality: L10n.realityPublicCharging
            ))
        }
        fears.append(FearRealityItem(
            fear: L10n.fearEvsUnreliable,
            reality: L10n.realityFewerParts
        ))
        fears.append(FearRealityItem(
            fear: L10n.fearCostsTooMuch,
            reality: L10n.realitySavePerYear(savingsRangeLower, savingsRangeUpper)
        ))
        
        let horizonYears = max(1, input.ownershipYears)
        var yearlyComparison: [YearlyComparison] = []
        for year in 1...horizonYears {
            let iceCost = result.yearlyIceCost * Double(year)
            let evCost = result.yearlyEvCost * Double(year)
            yearlyComparison.append(YearlyComparison(year: year, gasCost: iceCost, evCost: evCost))
        }
        
        return SimulationResult(
            verdict: verdict,
            weeklyCharges: weeklyCharges,
            yearlySavingsRange: savingsRangeLower...savingsRangeUpper,
            breakEvenMonths: breakEvenMonths,
            keyReasons: reasons,
            fearReality: fears,
            yearlyComparison: yearlyComparison,
            sourceYearlyBreakdown: result.sourceBreakdown,
            targetYearlyBreakdown: result.targetBreakdown
        )
    }

    private static func hasUsableConsumption(
        vehicle: VehicleCatalogItem,
        fuelOverrideLPerKm: Double?,
        energyOverrideKWhPerKm: Double?
    ) -> Bool {
        switch vehicle.powertrain {
        case .ice:
            let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm
            return (lPerKm ?? 0) > 0
        case .ev:
            let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm
            return (kWhPerKm ?? 0) > 0
        case .phev:
            let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm
            let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm
            return (lPerKm ?? 0) > 0 && (kWhPerKm ?? 0) > 0
        }
    }
}

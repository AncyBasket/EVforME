//
//  OperatingCostCalculator.swift
//  EVforME?
//
//  Unica fonte di €/km e €/anno di gestione (energia + bollo + manutenzione + RC).
//

import Foundation

enum OperatingCostCalculator {
    /// €/km di gestione allineato al simulatore (senza listino).
    static func operatingCostPerKm(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Double {
        let yearly = operatingCostPerYear(vehicle: vehicle, input: input, asSource: asSource)
        let km = max(1.0, Double(input.dailyKm))
        return yearly / km
    }

    /// €/anno di gestione (stessa base del verdetto).
    static func operatingCostPerYear(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Double {
        let simInput = makeSimulationInput(from: input)
        let scenario = input.scenario
        let currentYear = Defaults.referenceCalendarYear
        let yearlyKm = max(0, Double(input.dailyKm))

        let energy = EVSimulator().energyCostPerYear(
            vehicle: vehicle,
            input: simInput,
            scenario: scenario,
            fuelOverrideLPerKm: asSource ? simInput.iceFuelLPerKmOverride : nil,
            energyOverrideKWhPerKm: asSource ? nil : simInput.evKWhPerKmOverride,
            asSource: asSource
        )

        let listOrPaid = asSource ? input.sourcePurchasePrice : input.targetPurchasePrice
        let electrified = vehicle.powertrain == .ev || vehicle.powertrain == .phev
        let valueBasis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: listOrPaid,
            vehicleYear: vehicle.year,
            electrified: electrified,
            referenceYear: currentYear
        )
        let maintenance = OwnershipCostEstimates.maintenancePerYear(
            purchasePrice: valueBasis,
            vehicleAge: max(0, currentYear - vehicle.year),
            electrified: electrified,
            powertrain: vehicle.powertrain,
            yearlyKm: yearlyKm
        ) * (asSource ? scenario.iceCostMultiplier : scenario.evCostMultiplier)
        let taxes = OwnershipCostEstimates.bolloPerYearEstimate(
            catalogTaxesPerYear: vehicle.taxesPerYear,
            powertrain: vehicle.powertrain,
            vehicleYear: vehicle.year,
            referenceYear: currentYear
        )
        let insurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: valueBasis,
            yearlyKm: yearlyKm,
            electrified: electrified
        )
        return energy + maintenance + taxes + insurance
    }

    static func makeSimulationInput(from input: UserInput) -> EVSimulationInput {
        let iceOverride = input.sourceConsumptionOverrideLPer100Km.map { $0 / 100.0 }
        let evOverride = input.targetEnergyOverrideKWhPer100Km.map { $0 / 100.0 }
        let costs = OfficialCostService.shared.cachedOrBundledCosts()
        let petrol = costs?.pricePerLiter(for: .petrol) ?? max(input.fuelPrice, 1.85)
        var sim = EVSimulationInput(
            yearlyKm: Double(input.dailyKm),
            years: input.ownershipYears,
            fuelPricePerLiter: input.fuelPrice,
            electricityPricePerKWh: input.electricityPricePerKWh,
            areaType: input.areaType,
            tripProfile: input.tripProfile,
            hasHomeCharging: input.hasHomeCharging,
            sourcePurchasePrice: input.sourcePurchasePrice,
            targetPurchasePrice: input.targetPurchasePrice,
            comparisonIntent: input.comparisonIntent,
            iceFuelLPerKmOverride: iceOverride,
            evKWhPerKmOverride: evOverride,
            chargingConfiguration: input.resolvedChargingConfiguration()
        )
        sim.petrolPricePerLiter = petrol
        sim.catalogEnergyIsWallToWheel = true
        return sim
    }
}

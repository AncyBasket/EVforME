//
//  OperatingCostCalculator.swift
//  EVforME?
//
//  Unica fonte di €/km e €/anno di gestione (energia + bollo + manutenzione + RC).
//

import Foundation

enum OperatingCostCalculator {
    /// €/km di gestione. `nil` se i km sono 0 / quasi zero (niente divisione per 1).
    static func operatingCostPerKm(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Double? {
        guard input.dailyKm >= 100 else { return nil }
        let yearly = operatingCostPerYear(vehicle: vehicle, input: input, asSource: asSource)
        return yearly / Double(input.dailyKm)
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

    /// Prezzo benzina per la quota termica PHEV.
    /// Se l’utente ha personalizzato il prezzo e l’auto attuale è a benzina → usa quello;
    /// altrimenti MIMIT benzina (mai diesel/GPL dell’auto attuale).
    static func resolvePetrolPricePerLiter(for input: UserInput) -> Double {
        let costs = OfficialCostService.shared.cachedOrBundledCosts()
        let mimitPetrol = costs?.pricePerLiter(for: .petrol) ?? 1.85
        let sourceKind = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.resolvedFuelKind
        if StorageService.shared.hasUserCustomizedFuelPrice, sourceKind == .petrol {
            return max(0, input.fuelPrice)
        }
        return mimitPetrol
    }

    static func makeSimulationInput(from input: UserInput) -> EVSimulationInput {
        let iceOverride = input.sourceConsumptionOverrideLPer100Km.map { $0 / 100.0 }
        let evOverride = input.targetEnergyOverrideKWhPer100Km.map { $0 / 100.0 }
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
        sim.petrolPricePerLiter = resolvePetrolPricePerLiter(for: input)
        sim.catalogEnergyIsWallToWheel = true
        return sim
    }
}

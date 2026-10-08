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
        let maintenance = maintenancePerYear(
            vehicleAge: max(0, currentYear - vehicle.year),
            powertrain: vehicle.powertrain,
            yearlyKm: yearlyKm,
            market: input.market
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

    /// Manutenzione ordinaria (€/anno): tariffe `AppMarket` × età × km, con minimo annuo.
    ///
    /// Base: `MarketMaintenanceRates` (cluster IT/DE/UK/US).
    /// Età: moltiplicatori relativi Consumer Reports 2020 Table 2.1.
    /// HEV: tariffa a metà strada tra ICE e PHEV (stesso per i moltiplicatori età).
    static func maintenancePerYear(
        vehicleAge: Int,
        powertrain: Powertrain,
        yearlyKm: Double,
        market: AppMarket
    ) -> Double {
        let rates = MarketMaintenanceRates.rates(for: market)
        let ice = rates.iceEURPerYearAt15k
        let phev = rates.phevEURPerYearAt15k
        let ev = rates.evEURPerYearAt15k
        let hev = (ice + phev) / 2.0

        let baseAt15k: Double
        switch powertrain {
        case .ev: baseAt15k = ev
        case .phev: baseAt15k = phev
        case .hev: baseAt15k = hev
        case .ice: baseAt15k = ice
        }

        // CR 2020 Table 2.1: fasce miglia → moltiplicatore vs fascia media (50–100k).
        let iceYoung = 0.028 / 0.060
        let phevYoung = 0.021 / 0.031
        let evYoung = 0.012 / 0.028
        let iceOld = 0.079 / 0.060
        let phevOld = 0.033 / 0.031
        let evOld = 0.043 / 0.028

        let ageMultiplier: Double
        switch max(0, vehicleAge) {
        case 0..<4:
            switch powertrain {
            case .ev: ageMultiplier = evYoung
            case .phev: ageMultiplier = phevYoung
            case .hev: ageMultiplier = (iceYoung + phevYoung) / 2.0
            case .ice: ageMultiplier = iceYoung
            }
        case 4..<7:
            ageMultiplier = 1.0
        default:
            switch powertrain {
            case .ev: ageMultiplier = evOld
            case .phev: ageMultiplier = phevOld
            case .hev: ageMultiplier = (iceOld + phevOld) / 2.0
            case .ice: ageMultiplier = iceOld
            }
        }

        let km = max(0, yearlyKm)
        let raw = baseAt15k * ageMultiplier * (km / 15_000.0)

        let floor: Double
        switch powertrain {
        case .ice: floor = 180
        case .hev: floor = 150
        case .phev: floor = 150
        case .ev: floor = 80
        }
        return max(floor, raw)
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
        sim.market = input.market
        return sim
    }
}

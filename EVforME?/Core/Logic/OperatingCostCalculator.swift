//
//  OperatingCostCalculator.swift
//  EVforME?
//
//  Unica fonte di €/km e €/anno di gestione (energia + bollo + manutenzione + assicurazione).
//

import Foundation

enum OperatingCostCalculator {
    /// €/km di gestione. `nil` se km insufficienti o dati di calcolo mancanti/invalidi
    /// (niente energia “gratis” / totale parziale spacciato per completo).
    static func operatingCostPerKm(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Double? {
        guard input.dailyKm >= 100 else { return nil }
        guard let yearly = operatingCostPerYear(vehicle: vehicle, input: input, asSource: asSource) else {
            return nil
        }
        return yearly / Double(input.dailyKm)
    }

    /// €/anno di gestione (stessa base del verdetto). `nil` se i dati necessari non sono validi.
    static func operatingCostPerYear(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Double? {
        guard VehicleCalcDataGate.hasSufficientCalcData(
            vehicle: vehicle,
            input: input,
            asSource: asSource
        ) else {
            return nil
        }
        let simInput = makeSimulationInput(from: input)
        let scenario = input.scenario
        let currentYear = Defaults.referenceCalendarYear
        let yearlyKm = max(0, Double(input.dailyKm))
        let o = VehicleCalcDataGate.overrides(for: vehicle, input: input, asSource: asSource)

        let energy = EVSimulator().energyCostPerYear(
            vehicle: vehicle,
            input: simInput,
            scenario: scenario,
            fuelOverrideLPerKm: VehicleCalcDataGate.resolvedFuelLPerKm(
                vehicle: vehicle,
                overrideLPer100: o.fuelLPer100
            ),
            energyOverrideKWhPerKm: VehicleCalcDataGate.resolvedEnergyKWhPerKm(
                vehicle: vehicle,
                overrideKWhPer100: o.energyKWhPer100
            ),
            electricRangeKmOverride: VehicleCalcDataGate.resolvedElectricRangeKm(
                vehicle: vehicle,
                overrideKm: o.rangeKm
            ),
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
        // Stessa media del verdetto: totale orizzonte / anni di possesso.
        let years = max(1, input.ownershipYears)
        let bolloHorizon = OwnershipCostEstimates.bolloTotalOverHorizon(
            catalogTaxesPerYear: vehicle.taxesPerYear,
            powertrain: vehicle.powertrain,
            vehicleYear: vehicle.year,
            referenceYear: currentYear,
            ownershipYears: years,
            bookletPowerKwP2: asSource ? input.sourceBookletPowerKwP2 : input.targetBookletPowerKwP2,
            italianRegion: input.italianRegion,
            fuelKind: vehicle.resolvedFuelKind,
            catalogPowerKw: vehicle.powertrain == .ev ? nil : vehicle.powerKw
        )
        let taxes = bolloHorizon.amount / Double(years)
        let insurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: valueBasis,
            yearlyKm: yearlyKm,
            electrified: electrified,
            annualInsuranceOverrideEUR: input.annualInsuranceOverrideEUR,
            includeKaskoTheft: input.includeKaskoTheft,
            annualKaskoEUR: input.annualKaskoEUR
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

        // CR 2020 Table 2.1: fasce in miglia (0–50k / 50–100k / 100–200k), convertite
        // in km percorsi stimati = età × km annui (non anni calendari).
        let iceYoung = 0.028 / 0.060
        let phevYoung = 0.021 / 0.031
        let evYoung = 0.012 / 0.028
        let iceOld = 0.079 / 0.060
        let phevOld = 0.033 / 0.031
        let evOld = 0.043 / 0.028

        let km = max(0, yearlyKm)
        let lifetimeMiles = (Double(max(0, vehicleAge)) * km) / 1.60934
        let ageMultiplier: Double
        switch lifetimeMiles {
        case ..<50_000:
            switch powertrain {
            case .ev: ageMultiplier = evYoung
            case .phev: ageMultiplier = phevYoung
            case .hev: ageMultiplier = (iceYoung + phevYoung) / 2.0
            case .ice: ageMultiplier = iceYoung
            }
        case ..<100_000:
            ageMultiplier = 1.0
        default:
            switch powertrain {
            case .ev: ageMultiplier = evOld
            case .phev: ageMultiplier = phevOld
            case .hev: ageMultiplier = (iceOld + phevOld) / 2.0
            case .ice: ageMultiplier = iceOld
            }
        }

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
        let mimitPetrol = costs?.pricePerLiter(for: .petrol) ?? OfficialEnergyCosts.Fallback.petrolPerLiter
        let sourceKind = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.resolvedFuelKind
        if StorageService.shared.hasUserCustomizedFuelPrice, sourceKind == .petrol {
            return max(0, input.fuelPrice)
        }
        return mimitPetrol
    }

    static func makeSimulationInput(from input: UserInput) -> EVSimulationInput {
        // Solo override che passano il gate condiviso: valori invalidi non entrano nei costi.
        let catalog = VehicleCatalogService.shared
        let source = catalog.vehicle(by: input.sourceVehicleId)
        let target = catalog.vehicle(by: input.targetVehicleId)
        let iceOverride = source.flatMap {
            VehicleCalcDataGate.resolvedFuelLPerKm(
                vehicle: $0,
                overrideLPer100: input.sourceConsumptionOverrideLPer100Km
            )
        }
        let evOverride = target.flatMap {
            VehicleCalcDataGate.resolvedEnergyKWhPerKm(
                vehicle: $0,
                overrideKWhPer100: input.targetEnergyOverrideKWhPer100Km
            )
        }
        let sourceEnergyOverride = source.flatMap {
            VehicleCalcDataGate.resolvedEnergyKWhPerKm(
                vehicle: $0,
                overrideKWhPer100: input.sourceEnergyOverrideKWhPer100Km
            )
        }
        let targetFuelOverride = target.flatMap {
            VehicleCalcDataGate.resolvedFuelLPerKm(
                vehicle: $0,
                overrideLPer100: input.targetFuelConsumptionOverrideLPer100Km
            )
        }
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
            sourceEnergyKWhPerKmOverride: sourceEnergyOverride,
            targetFuelLPerKmOverride: targetFuelOverride,
            sourceElectricRangeKmOverride: source.flatMap {
                VehicleCalcDataGate.resolvedElectricRangeKm(
                    vehicle: $0,
                    overrideKm: input.sourceElectricRangeOverrideKm
                )
            },
            targetElectricRangeKmOverride: target.flatMap {
                VehicleCalcDataGate.resolvedElectricRangeKm(
                    vehicle: $0,
                    overrideKm: input.targetElectricRangeOverrideKm
                )
            },
            chargingConfiguration: input.resolvedChargingConfiguration()
        )
        sim.petrolPricePerLiter = resolvePetrolPricePerLiter(for: input)
        sim.catalogEnergyIsWallToWheel = true
        sim.market = input.market
        sim.annualInsuranceOverrideEUR = input.annualInsuranceOverrideEUR
        sim.includeKaskoTheft = input.includeKaskoTheft
        sim.annualKaskoEUR = input.annualKaskoEUR
        sim.sourceBookletPowerKwP2 = input.sourceBookletPowerKwP2
        sim.targetBookletPowerKwP2 = input.targetBookletPowerKwP2
        sim.italianRegion = input.italianRegion
        return sim
    }
}

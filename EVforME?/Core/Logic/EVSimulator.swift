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
    var comparisonIntent: ComparisonIntent = .alreadyOwned
    /// L/km override (già convertito da L/100 km).
    var iceFuelLPerKmOverride: Double? = nil
    /// kWh/km override (già convertito da kWh/100 km).
    var evKWhPerKmOverride: Double? = nil
    /// Configurazione ricarica personalizzata
    var chargingConfiguration: ChargingConfiguration = ChargingConfiguration()
    /// Prezzo benzina (€/L) per la quota termica delle PHEV (mai il carburante dell’auto attuale).
    var petrolPricePerLiter: Double = OfficialEnergyCosts.Fallback.petrolPerLiter
    /// Se `false`, il consumo EV è battery-side e si applica l’efficienza di ricarica.
    /// Default `true`: catalogo WLTP EU = wall-to-wheel (perdite già incluse).
    var catalogEnergyIsWallToWheel: Bool = true
    /// Paese per tariffe manutenzione (ISO → AppMarket).
    var market: AppMarket = .IT
    /// Override RC annuale (€); `nil`/≤0 = media IVASS per entrambe.
    var annualInsuranceOverrideEUR: Double? = nil
    /// Kasko/furto (OFF di default); richiede importo utente.
    var includeKaskoTheft: Bool = false
    var annualKaskoEUR: Double? = nil
    /// kW P.2 a libretto — auto attuale (se EV).
    var sourceBookletPowerKwP2: Double? = nil
    /// kW P.2 a libretto — EV target.
    var targetBookletPowerKwP2: Double? = nil
    /// Regione IT per tariffa bollo EV (opzionale).
    var italianRegion: ItalianRegion = .unspecified
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
    /// `false` se il bollo EV post-5 anni non è stimabile (manca P.2 a libretto).
    let taxesKnown: Bool

    init(
        energy: Double,
        maintenance: Double,
        taxes: Double,
        insurance: Double,
        taxesKnown: Bool = true
    ) {
        self.energy = energy
        self.maintenance = maintenance
        self.taxes = taxes
        self.insurance = insurance
        self.taxesKnown = taxesKnown
    }

    var total: Double { energy + maintenance + taxes + insurance }
}

enum OwnershipCostEstimates {
    /// Valore di riferimento per assicurazione/manutenzione.
    ///
    /// `Defaults.suggestedPurchasePrice` è già una stima **usato** (sconta l’età).
    /// Se trattassimo quel prezzo come listino nuovo e lo svalutassimo di nuovo,
    /// RC/manutenzione crollerebbero al floor (doppia svalutazione).
    /// Haircut solo quando il prezzo sembra ancora un listino/nuovo per un’auto datata.
    static func operatingValueBasis(
        purchaseOrListPrice: Double,
        vehicleYear: Int,
        electrified: Bool,
        referenceYear: Int = Calendar.current.component(.year, from: Date())
    ) -> Double {
        let age = max(0, referenceYear - vehicleYear)
        if age <= 0 {
            return purchaseOrListPrice
        }
        let floor: Double = electrified ? 8_000 : 3_500
        // Stessa curva grezza di `Defaults.suggestedPurchasePrice` (±15% tolleranza).
        let typicalUsed: Double = electrified
            ? max(14_000, 38_000 - Double(age) * 1_300)
            : max(3_500, 16_500 - Double(age) * 900)
        if purchaseOrListPrice <= typicalUsed * 1.15 {
            return max(floor, purchaseOrListPrice)
        }
        let residual = residualValue(
            purchasePrice: purchaseOrListPrice,
            years: age,
            electrified: electrified
        )
        return max(floor, min(purchaseOrListPrice, residual))
    }

    /// Media IVASS premio RC auto (2° trim. 2026) — uguale per auto attuale ed EV.
    static let ivassAverageRCEURPerYear: Double = 422

    /// Assicurazione annua: RC flat IVASS (o override utente) + kasko/furto solo se l’utente indica l’importo.
    /// Nessun proxy % sul valore: se kasko è ON senza importo, la UI deve chiederlo (qui si ignora la kasko).
    static func insurancePerYear(
        purchasePrice: Double,
        yearlyKm: Double,
        electrified: Bool,
        annualInsuranceOverrideEUR: Double? = nil,
        includeKaskoTheft: Bool = false,
        annualKaskoEUR: Double? = nil
    ) -> Double {
        _ = purchasePrice
        _ = yearlyKm
        _ = electrified
        let rc: Double
        if let override = annualInsuranceOverrideEUR, override > 0 {
            rc = override
        } else {
            rc = ivassAverageRCEURPerYear
        }
        guard includeKaskoTheft, let kasko = annualKaskoEUR, kasko > 0 else { return rc }
        return rc + kasko
    }

    /// Bollo / tassa di possesso — stima semplificata (non ACI ufficiale).
    /// EV: 5 anni esenzione nazionale, poi **1/4 × tariffa regionale lineare €/kW × P.2 a libretto**.
    /// Nessuna fascia 3,87 €/kW oltre 100 kW per le EV (quella vale per benzina/diesel).
    /// 2,58 €/kW è stima nazionale di ripiego: Lazio 2,84, Lombardia/Piemonte 0 €, ecc. (ACI 2026).
    /// Non usare EEA `ep__KW_` (picco) né inventare 0 € in silenzio: senza P.2 o senza tariffa → `isKnown = false`.
    /// ICE/HEV/PHEV: tariffario regionale 2026 citato (es. Molise) se `powerKw` noto; altrimenti `taxesPerYear` catalogo (stima nazionale 2,58/3,87).
    static let nationalEVBolloEURPerKw: Double = 2.58

    struct BolloEstimate: Equatable {
        let amount: Double
        /// `false` quando non stimabile (EV post-5y senza P.2/tariffa, o ICE/HEV/PHEV senza bollo catalogo).
        let isKnown: Bool
    }

    static func bolloPerYearEstimate(
        catalogTaxesPerYear: Double,
        powertrain: Powertrain,
        vehicleYear: Int,
        referenceYear: Int = Calendar.current.component(.year, from: Date()),
        bookletPowerKwP2: Double? = nil,
        italianRegion: ItalianRegion = .unspecified,
        fuelKind: FuelKind = .petrol,
        catalogPowerKw: Double? = nil
    ) -> Double {
        bolloPerYearDetail(
            catalogTaxesPerYear: catalogTaxesPerYear,
            powertrain: powertrain,
            vehicleYear: vehicleYear,
            referenceYear: referenceYear,
            bookletPowerKwP2: bookletPowerKwP2,
            italianRegion: italianRegion,
            fuelKind: fuelKind,
            catalogPowerKw: catalogPowerKw
        ).amount
    }

    static func bolloPerYearDetail(
        catalogTaxesPerYear: Double,
        powertrain: Powertrain,
        vehicleYear: Int,
        referenceYear: Int = Calendar.current.component(.year, from: Date()),
        bookletPowerKwP2: Double? = nil,
        italianRegion: ItalianRegion = .unspecified,
        fuelKind: FuelKind = .petrol,
        catalogPowerKw: Double? = nil
    ) -> BolloEstimate {
        let age = max(0, referenceYear - vehicleYear)
        switch powertrain {
        case .ev:
            if italianRegion.evPermanentlyExempt {
                return BolloEstimate(amount: 0, isKnown: true)
            }
            let exemptYears = italianRegion.evExemptionYears(forVehicleYear: vehicleYear)
            if age < exemptYears { return BolloEstimate(amount: 0, isKnown: true) }
            guard let rate = italianRegion.evBolloEURPerKw else {
                return BolloEstimate(amount: 0, isKnown: false)
            }
            if let kw = bookletPowerKwP2, kw > 0 {
                // Lineare: nessun salto 3,87 oltre 100 kW (solo ICE). Es. naz. 100 kW → 2,58×100×1/4 = 64,50.
                // Sicilia: clausola ACI «a prescindere» a 2,58 €/kW → rate×kW×1/4.
                let raw = rate * kw * 0.25
                return BolloEstimate(amount: (raw * 100).rounded() / 100, isKnown: true)
            }
            return BolloEstimate(amount: 0, isKnown: false)
        case .phev, .hev, .ice:
            let kw = bookletPowerKwP2 ?? catalogPowerKw
            if let kw, kw > 0,
               let regional = italianRegion.thermalBolloEUR(
                powerKw: kw,
                fuelKind: fuelKind,
                vehicleYear: vehicleYear,
                referenceYear: referenceYear
               ) {
                return BolloEstimate(amount: regional, isKnown: true)
            }
            // Senza kW (P.2 / catalogo) o senza tariffario regionale → bollo catalogo (stima nazionale).
            if catalogTaxesPerYear > 0 {
                return BolloEstimate(amount: catalogTaxesPerYear, isKnown: true)
            }
            return BolloEstimate(amount: 0, isKnown: false)
        }
    }

    /// Somma bollo anno per anno sull’orizzonte (EV può uscire dall’esenzione a metà periodo).
    static func bolloTotalOverHorizon(
        catalogTaxesPerYear: Double,
        powertrain: Powertrain,
        vehicleYear: Int,
        referenceYear: Int,
        ownershipYears: Int,
        bookletPowerKwP2: Double? = nil,
        italianRegion: ItalianRegion = .unspecified,
        fuelKind: FuelKind = .petrol,
        catalogPowerKw: Double? = nil
    ) -> BolloEstimate {
        let years = max(1, ownershipYears)
        var sum = 0.0
        var known = true
        for offset in 0..<years {
            let detail = bolloPerYearDetail(
                catalogTaxesPerYear: catalogTaxesPerYear,
                powertrain: powertrain,
                vehicleYear: vehicleYear,
                referenceYear: referenceYear + offset,
                bookletPowerKwP2: bookletPowerKwP2,
                italianRegion: italianRegion,
                fuelKind: fuelKind,
                catalogPowerKw: catalogPowerKw
            )
            sum += detail.amount
            if !detail.isKnown { known = false }
        }
        return BolloEstimate(amount: (sum * 100).rounded() / 100, isKnown: known)
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
    
    /// Manutenzione ordinaria — unica fonte: `OperatingCostCalculator.maintenancePerYear`.
    static func maintenancePerYear(
        vehicleAge: Int,
        powertrain: Powertrain,
        yearlyKm: Double,
        market: AppMarket = .IT,
        purchasePrice: Double = 0,
        electrified: Bool = false
    ) -> Double {
        _ = purchasePrice
        _ = electrified
        return OperatingCostCalculator.maintenancePerYear(
            vehicleAge: vehicleAge,
            powertrain: powertrain,
            yearlyKm: yearlyKm,
            market: market
        )
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

        // Sempre valore d’uso (età): un’usata di 10 anni pesa di più in RC/manutenzione,
        // senza gonfiare l’EV col listino nuovo.
        let refYear = Defaults.referenceCalendarYear
        let sourceValueBasis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: input.sourcePurchasePrice,
            vehicleYear: sourceVehicle.year,
            electrified: sourceVehicle.powertrain == .ev || sourceVehicle.powertrain == .phev,
            referenceYear: refYear
        )
        let targetValueBasis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: input.targetPurchasePrice,
            vehicleYear: targetVehicle.year,
            electrified: true,
            referenceYear: refYear
        )

        let sourceInsurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: sourceValueBasis,
            yearlyKm: yearlyKm,
            electrified: sourceVehicle.powertrain == .ev || sourceVehicle.powertrain == .phev,
            annualInsuranceOverrideEUR: input.annualInsuranceOverrideEUR,
            includeKaskoTheft: input.includeKaskoTheft,
            annualKaskoEUR: input.annualKaskoEUR
        )
        let targetInsurance = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: targetValueBasis,
            yearlyKm: yearlyKm,
            electrified: true,
            annualInsuranceOverrideEUR: input.annualInsuranceOverrideEUR,
            includeKaskoTheft: input.includeKaskoTheft,
            annualKaskoEUR: input.annualKaskoEUR
        )

        let currentYear = Defaults.referenceCalendarYear
        let sourceMaintenance = OwnershipCostEstimates.maintenancePerYear(
            vehicleAge: max(0, currentYear - sourceVehicle.year),
            powertrain: sourceVehicle.powertrain,
            yearlyKm: yearlyKm,
            market: input.market
        ) * scenario.iceCostMultiplier
        let targetMaintenance = OwnershipCostEstimates.maintenancePerYear(
            vehicleAge: max(0, currentYear - targetVehicle.year),
            powertrain: targetVehicle.powertrain,
            yearlyKm: yearlyKm,
            market: input.market
        ) * scenario.evCostMultiplier

        // Bollo pluriennale (EV può uscire dall’esenzione a metà orizzonte) → media annua per verdetto/break-even.
        let sourceBolloHorizon = OwnershipCostEstimates.bolloTotalOverHorizon(
            catalogTaxesPerYear: sourceVehicle.taxesPerYear,
            powertrain: sourceVehicle.powertrain,
            vehicleYear: sourceVehicle.year,
            referenceYear: currentYear,
            ownershipYears: years,
            bookletPowerKwP2: input.sourceBookletPowerKwP2,
            italianRegion: input.italianRegion,
            fuelKind: sourceVehicle.resolvedFuelKind,
            catalogPowerKw: sourceVehicle.powertrain == .ev ? nil : sourceVehicle.powerKw
        )
        let targetBolloHorizon = OwnershipCostEstimates.bolloTotalOverHorizon(
            catalogTaxesPerYear: targetVehicle.taxesPerYear,
            powertrain: targetVehicle.powertrain,
            vehicleYear: targetVehicle.year,
            referenceYear: currentYear,
            ownershipYears: years,
            bookletPowerKwP2: input.targetBookletPowerKwP2,
            italianRegion: input.italianRegion,
            fuelKind: targetVehicle.resolvedFuelKind,
            catalogPowerKw: targetVehicle.powertrain == .ev ? nil : targetVehicle.powerKw
        )
        let yearsD = Double(max(1, years))
        let sourceBolloAvg = sourceBolloHorizon.amount / yearsD
        let targetBolloAvg = targetBolloHorizon.amount / yearsD
        let sourceBreakdown = OperatingCostBreakdown(
            energy: sourceEnergy,
            maintenance: sourceMaintenance,
            taxes: sourceBolloAvg,
            insurance: sourceInsurance,
            taxesKnown: sourceBolloHorizon.isKnown
        )
        let targetBreakdown = OperatingCostBreakdown(
            energy: targetEnergy,
            maintenance: targetMaintenance,
            taxes: targetBolloAvg,
            insurance: targetInsurance,
            taxesKnown: targetBolloHorizon.isKnown
        )

        let yearlyIceCost = sourceBreakdown.total
        let yearlyEvCost = targetBreakdown.total

        let iceTotalCost = yearlyIceCost * yearsD
        let evTotalCost = yearlyEvCost * yearsD
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

    /// Costo energia annuo (unica formula condivisa con `OperatingCostCalculator`).
    func energyCostPerYear(
        vehicle: VehicleCatalogItem,
        input: EVSimulationInput,
        scenario: Scenario,
        fuelOverrideLPerKm: Double?,
        energyOverrideKWhPerKm: Double?,
        asSource: Bool
    ) -> Double {
        let yearlyKm = max(0, input.yearlyKm)
        let area = input.areaType
        let trip = input.tripProfile
        let fuelMult = asSource ? scenario.iceCostMultiplier : scenario.evCostMultiplier
        let elecMult = asSource ? scenario.iceCostMultiplier : scenario.evCostMultiplier
        let wallToWheel = input.catalogEnergyIsWallToWheel

        switch vehicle.powertrain {
        case .ice, .hev:
            guard let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm, lPerKm > 0 else {
                return 0
            }
            // Per CNG, fuelConsumptionLPerKm è in kg/km e fuelPricePerLiter è €/kg.
            return yearlyKm
                * lPerKm
                * area.fuelConsumptionMultiplier(for: vehicle.powertrain)
                * trip.iceExtraMultiplier
                * max(0, input.fuelPricePerLiter)
                * fuelMult

        case .ev:
            guard let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm, kWhPerKm > 0 else {
                return 0
            }
            let annual = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm,
                energyConsumptionKWhPerKm: kWhPerKm,
                chargingConfig: input.chargingConfiguration,
                consumptionIsWallToWheel: wallToWheel
            )
            return annual
                * area.evConsumptionMultiplier
                * trip.evExtraMultiplier
                * elecMult

        case .phev:
            let share = vehicle.phevElectricKmShare(
                hasHomeCharging: input.hasHomeCharging,
                yearlyKm: yearlyKm
            )
            guard let lPerKm = fuelOverrideLPerKm ?? vehicle.fuelConsumptionLPerKm, lPerKm > 0 else {
                return 0
            }
            guard let kWhPerKm = energyOverrideKWhPerKm ?? vehicle.resolvedEnergyKWhPerKm, kWhPerKm > 0 else {
                return 0
            }
            // PHEV: sempre benzina (o fuelKind della PHEV), mai il carburante dell’auto attuale.
            let phevFuelPrice = max(0, input.petrolPricePerLiter)
            let fuelPart = yearlyKm * (1.0 - share)
                * lPerKm
                * area.iceConsumptionMultiplier
                * trip.iceExtraMultiplier
                * phevFuelPrice
                * fuelMult
            let elecPart = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm * share,
                energyConsumptionKWhPerKm: kWhPerKm,
                chargingConfig: input.chargingConfiguration,
                consumptionIsWallToWheel: wallToWheel
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
        let simulationInput = OperatingCostCalculator.makeSimulationInput(from: input)
        
        let selectedScenario = scenario ?? input.scenario
        
        AppLogger.shared.info("Simulating: \(sourceVehicle.displayName) -> \(targetVehicle.displayName)", category: .simulation)
        
        let result = simulator.simulate(
            input: simulationInput,
            scenario: selectedScenario,
            sourceVehicle: sourceVehicle,
            targetVehicle: targetVehicle
        )
        
        let yearlyKm = Double(input.dailyKm)
        let electricShare: Double
        switch targetVehicle.powertrain {
        case .phev:
            electricShare = targetVehicle.phevElectricKmShare(
                hasHomeCharging: input.hasHomeCharging,
                yearlyKm: yearlyKm
            )
        case .ev:
            electricShare = 1.0
        case .ice, .hev:
            electricShare = 0
        }
        let weeklyCharges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: yearlyKm,
            powertrain: targetVehicle.powertrain,
            rangeKm: WeeklyChargeEstimator.declaredRangeKm(for: targetVehicle),
            electricKmShare: electricShare
        )
        
        let yearlySavings = result.yearlyIceCost - result.yearlyEvCost
        let savingsBandLow = Int(yearlySavings * 0.9)
        let savingsBandHigh = Int(yearlySavings * 1.1)
        let savingsRangeLower = min(savingsBandLow, savingsBandHigh)
        let savingsRangeUpper = max(savingsBandLow, savingsBandHigh)

        let purchasePremium = input.netPurchasePremiumEUR
        let breakEvenMonths: Int?
        if input.comparisonIntent == .alreadyOwned {
            breakEvenMonths = nil
        } else if yearlySavings > 50, purchasePremium > 0 {
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
            ownershipYears: input.ownershipYears,
            comparisonIntent: input.comparisonIntent
        )

        AppLogger.shared.info(
            "Simulation complete: verdict=\(verdict.rawValue), savings=\(String(format: "%.2f", yearlySavings))€/year",
            category: .simulation
        )

        var reasons = [
            L10n.switchingFromTo(sourceVehicle.displayName, targetVehicle.displayName),
            L10n.chargePerWeekLine(weeklyCharges),
            yearlySavings > 0
                ? L10n.saveUpToPerYear(Int(yearlySavings))
                : L10n.saveCurrentCheaper,
            input.hasHomeCharging
                ? L10n.homeChargingEasier
                : L10n.publicChargingManageable
        ]
        if targetVehicle.powertrain == .phev {
            reasons.append(L10n.phevBlendReason)
        }
        reasons.append(L10n.insuranceIncludedReason)
        switch input.comparisonIntent {
        case .alreadyOwned:
            reasons.append(L10n.comparisonIntentOwnedReason)
        case .consideringPurchase:
            if input.includeIncentives {
                reasons.append(L10n.incentivesIncludedReason(Int(input.estimatedPurchaseIncentiveEUR)))
            }
        }
        if input.sourceConsumptionOverrideLPer100Km != nil || input.targetEnergyOverrideKWhPer100Km != nil {
            reasons.append(L10n.stickerOverrideAppliedReason)
        }
        // Verdetto = solo gestione; il listino (se presente) è solo nota a parte.
        if yearlySavings > 50 {
            reasons.append(L10n.opexSavingsOnlyReason(Int(yearlySavings)))
        } else if input.comparisonIntent == .consideringPurchase {
            reasons.append(L10n.breakEvenNotReachedReason)
        } else {
            // Già posseduta: niente “maggior costo di acquisto” — solo opex.
            reasons.append(
                yearlySavings > 0
                    ? L10n.opexSavingsLimitedReason(Int(yearlySavings))
                    : L10n.saveCurrentCheaper
            )
        }
        if input.comparisonIntent == .consideringPurchase, let breakEvenMonths {
            reasons.append(L10n.breakEvenMonthsReason(breakEvenMonths))
        }

        var fears: [FearRealityItem] = []
        if let chargingReality = ChargingFearCopy.reality(for: weeklyCharges) {
            fears.append(FearRealityItem(
                fear: L10n.fearRunOutBattery,
                reality: chargingReality
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
            reality: yearlySavings > 0
                ? L10n.realitySavePerYear(savingsRangeLower, savingsRangeUpper)
                : L10n.realityCurrentCheaper
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
        case .ice, .hev:
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

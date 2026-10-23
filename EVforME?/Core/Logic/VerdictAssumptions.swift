//
//  VerdictAssumptions.swift
//  EVforME?
//
//  Testi “Assunzioni” del verdetto — stessi consumi/prezzi del simulatore.
//

import Foundation

enum VerdictAssumptions {
    /// Valori effettivi usati nel calcolo (catalogo × area/tragitto/scenario + elettricità pesata).
    struct Snapshot: Equatable {
        /// L/100 km dopo moltiplicatori area/tragitto/scenario (nil se catalogo assente).
        let sourceLPer100KmEffective: Double?
        /// kWh/100 km dopo moltiplicatori area/tragitto/scenario (nil se catalogo assente).
        let targetKWhPer100KmEffective: Double?
        let fuelPricePerLiter: Double
        /// Media ponderata casa/pubblico (stesso `weightedCostPerKWh` del calcolo).
        let electricityWeightedPerKWh: Double
        let hasHomeCharging: Bool
        let homeShare: Double
        let homePricePerKWh: Double
        let publicPricePerKWh: Double
    }

    /// Consumo ICE/HEV effettivo (L o kg per km) dopo i correttivi di `energyCostPerYear`.
    static func effectiveSourceFuelPerKm(
        catalogLPerKm: Double,
        powertrain: Powertrain,
        areaType: AreaType,
        tripProfile: TripProfile,
        scenario: Scenario
    ) -> Double {
        catalogLPerKm
            * areaType.fuelConsumptionMultiplier(for: powertrain)
            * tripProfile.iceExtraMultiplier
            * scenario.iceCostMultiplier
    }

    /// Consumo EV effettivo (kWh per km) dopo i correttivi di `energyCostPerYear`.
    static func effectiveTargetEnergyPerKm(
        catalogKWhPerKm: Double,
        areaType: AreaType,
        tripProfile: TripProfile,
        scenario: Scenario
    ) -> Double {
        catalogKWhPerKm
            * areaType.evConsumptionMultiplier
            * tripProfile.evExtraMultiplier
            * scenario.evCostMultiplier
    }

    static func snapshot(
        userInput: UserInput,
        catalog: VehicleCatalogService = .shared
    ) -> Snapshot {
        let source = catalog.vehicle(by: userInput.sourceVehicleId)
        let target = catalog.vehicle(by: userInput.targetVehicleId)
        let charging = userInput.resolvedChargingConfiguration()
        let homePrice = charging.customHomePricePerKWh ?? charging.homeChargingType.baseCostPerKWh
        let publicPrice = charging.customPublicPricePerKWh ?? charging.publicChargingType.baseCostPerKWh
        let homeShare = charging.hasHomeCharging ? charging.homeChargingShare : 0.0

        let sourceL100: Double? = {
            let lPerKm: Double?
            let powertrain: Powertrain
            if let o = userInput.sourceConsumptionOverrideLPer100Km, o > 0 {
                lPerKm = o / 100.0
                powertrain = source?.powertrain ?? .ice
            } else if let s = source, let catalog = s.fuelConsumptionLPerKm, catalog > 0 {
                lPerKm = catalog
                powertrain = s.powertrain
            } else {
                return nil
            }
            guard let lPerKm else { return nil }
            return effectiveSourceFuelPerKm(
                catalogLPerKm: lPerKm,
                powertrain: powertrain,
                areaType: userInput.areaType,
                tripProfile: userInput.tripProfile,
                scenario: userInput.scenario
            ) * 100
        }()

        let targetKWh100: Double? = {
            let raw: Double? = {
                if let o = userInput.targetEnergyOverrideKWhPer100Km, o > 0 { return o / 100.0 }
                guard let kWhPerKm = target?.resolvedEnergyKWhPerKm, kWhPerKm > 0 else { return nil }
                return kWhPerKm
            }()
            guard let kWhPerKm = raw else { return nil }
            return effectiveTargetEnergyPerKm(
                catalogKWhPerKm: kWhPerKm,
                areaType: userInput.areaType,
                tripProfile: userInput.tripProfile,
                scenario: userInput.scenario
            ) * 100
        }()

        return Snapshot(
            sourceLPer100KmEffective: sourceL100,
            targetKWhPer100KmEffective: targetKWh100,
            fuelPricePerLiter: userInput.fuelPrice,
            electricityWeightedPerKWh: charging.weightedCostPerKWh(),
            hasHomeCharging: charging.hasHomeCharging,
            homeShare: homeShare,
            homePricePerKWh: homePrice,
            publicPricePerKWh: publicPrice
        )
    }

    static func consumptionSourceLine(from snap: Snapshot) -> String {
        if let l100 = snap.sourceLPer100KmEffective {
            return L10n.assumptionConsumptionSourceEffectiveFormat(l100)
        }
        return L10n.assumptionConsumptionSourceUnknown
    }

    static func consumptionTargetLine(from snap: Snapshot) -> String {
        if let kWh = snap.targetKWhPer100KmEffective {
            return L10n.assumptionConsumptionTargetEffectiveFormat(kWh)
        }
        return L10n.assumptionConsumptionTargetUnknown
    }

    static func fuelPriceLine(from snap: Snapshot) -> String {
        L10n.assumptionFuelPriceFormat(snap.fuelPricePerLiter)
    }

    static func electricityLine(from snap: Snapshot) -> String {
        if snap.hasHomeCharging, snap.homeShare > 0, snap.homeShare < 1 {
            let homePct = Int((snap.homeShare * 100).rounded())
            let publicPct = max(0, 100 - homePct)
            return L10n.assumptionElectricityWeightedFormat(
                snap.homePricePerKWh,
                homePct,
                snap.publicPricePerKWh,
                publicPct,
                snap.electricityWeightedPerKWh
            )
        }
        if snap.hasHomeCharging, snap.homeShare >= 1 {
            return L10n.assumptionElectricityHomeOnlyFormat(snap.homePricePerKWh)
        }
        return L10n.assumptionElectricityPublicOnlyFormat(snap.publicPricePerKWh)
    }
}

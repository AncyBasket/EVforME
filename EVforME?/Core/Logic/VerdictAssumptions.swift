//
//  VerdictAssumptions.swift
//  EVforME?
//
//  Testi “Assunzioni” del verdetto — stessi consumi/prezzi del simulatore.
//

import Foundation

enum VerdictAssumptions {
    /// Valori effettivi usati nel calcolo (override OCR / slider / catalogo).
    struct Snapshot: Equatable {
        let sourceLPer100Km: Double?
        let targetKWhPer100Km: Double?
        let fuelPricePerLiter: Double
        let electricityPricePerKWh: Double
    }

    static func snapshot(
        userInput: UserInput,
        catalog: VehicleCatalogService = .shared
    ) -> Snapshot {
        let source = catalog.vehicle(by: userInput.sourceVehicleId)
        let target = catalog.vehicle(by: userInput.targetVehicleId)
        let sourceL100: Double? = {
            if let o = userInput.sourceConsumptionOverrideLPer100Km, o > 0 { return o }
            guard let lPerKm = source?.fuelConsumptionLPerKm, lPerKm > 0 else { return nil }
            return lPerKm * 100
        }()
        let targetKWh100: Double? = {
            if let o = userInput.targetEnergyOverrideKWhPer100Km, o > 0 { return o }
            guard let kWhPerKm = target?.resolvedEnergyKWhPerKm, kWhPerKm > 0 else { return nil }
            return kWhPerKm * 100
        }()
        return Snapshot(
            sourceLPer100Km: sourceL100,
            targetKWhPer100Km: targetKWh100,
            fuelPricePerLiter: userInput.fuelPrice,
            electricityPricePerKWh: userInput.electricityPricePerKWh
        )
    }

    static func consumptionSourceLine(from snap: Snapshot) -> String {
        if let l100 = snap.sourceLPer100Km {
            return L10n.assumptionConsumptionSourceFormat(l100)
        }
        return L10n.assumptionConsumptionSourceUnknown
    }

    static func consumptionTargetLine(from snap: Snapshot) -> String {
        if let kWh = snap.targetKWhPer100Km {
            return L10n.assumptionConsumptionTargetFormat(kWh)
        }
        return L10n.assumptionConsumptionTargetUnknown
    }

    static func fuelPriceLine(from snap: Snapshot) -> String {
        L10n.assumptionFuelPriceFormat(snap.fuelPricePerLiter)
    }

    static func electricityLine(from snap: Snapshot) -> String {
        L10n.assumptionElectricityFormat(snap.electricityPricePerKWh)
    }
}

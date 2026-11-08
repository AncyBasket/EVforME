//
//  VehicleCalcDataGate.swift
//  EVforME?
//
//  Controlli condivisi di sufficienza/validità per prompt incompleti,
//  anteprima €/km e verdetto. Stessi intervalli di InputValidator.
//

import Foundation

enum VehicleCalcDataGate {
    /// Intervallo sticker L/100 (ICE/HEV/PHEV CS override).
    static let fuelLPer100Range: ClosedRange<Double> = 2...25
    /// PHEV charge-sustaining minimo usabile nei calcoli (anti ponderato EEA).
    static let phevFuelLPer100Minimum: Double = 3.0
    /// Intervallo sticker kWh/100 (EV/PHEV CD override).
    static let energyKWhPer100Range: ClosedRange<Double> = 8...40

    // MARK: - Field validators (unità UI: L/100, kWh/100, km)

    static func isValidFuelLPer100(_ raw: Double?, powertrain: Powertrain) -> Bool {
        guard let raw, raw.isFinite, fuelLPer100Range.contains(raw) else { return false }
        if powertrain == .phev, raw < phevFuelLPer100Minimum { return false }
        return true
    }

    static func isValidEnergyKWhPer100(_ raw: Double?) -> Bool {
        guard let raw, raw.isFinite, energyKWhPer100Range.contains(raw) else { return false }
        return true
    }

    static func isValidElectricRangeKm(_ raw: Double?) -> Bool {
        EVSimulator.validElectricRangeKm(raw) != nil
    }

    // MARK: - Resolved usable values (L/km, kWh/km, km)

    /// CS fuel L/km usabile: override valido, altrimenti catalogo usabile.
    static func resolvedFuelLPerKm(
        vehicle: VehicleCatalogItem,
        overrideLPer100: Double?
    ) -> Double? {
        if let overrideLPer100 {
            guard isValidFuelLPer100(overrideLPer100, powertrain: vehicle.powertrain) else {
                return nil
            }
            return overrideLPer100 / 100.0
        }
        switch vehicle.powertrain {
        case .phev:
            return vehicle.usableChargeSustainingFuelLPerKm
        case .ice, .hev:
            guard let fuel = vehicle.fuelConsumptionLPerKm, fuel > 0, fuel.isFinite else { return nil }
            return fuel
        case .ev:
            return nil
        }
    }

    /// CD / EV energy kWh/km usabile: override valido, altrimenti catalogo non ponderato.
    static func resolvedEnergyKWhPerKm(
        vehicle: VehicleCatalogItem,
        overrideKWhPer100: Double?
    ) -> Double? {
        if let overrideKWhPer100 {
            guard isValidEnergyKWhPer100(overrideKWhPer100) else { return nil }
            return overrideKWhPer100 / 100.0
        }
        guard let kWh = vehicle.usableChargeDepletingEnergyKWhPerKm, kWh > 0, kWh.isFinite else {
            return nil
        }
        return kWh
    }

    static func resolvedElectricRangeKm(
        vehicle: VehicleCatalogItem,
        overrideKm: Double?
    ) -> Double? {
        if let overrideKm {
            return EVSimulator.validElectricRangeKm(overrideKm)
        }
        return vehicle.catalogPHEVElectricRangeKm
    }

    // MARK: - Needs-* (prompt: resta editabile finché non valido)

    static func needsFuel(
        vehicle: VehicleCatalogItem,
        overrideLPer100: Double?
    ) -> Bool {
        switch vehicle.powertrain {
        case .ice, .hev, .phev:
            return resolvedFuelLPerKm(vehicle: vehicle, overrideLPer100: overrideLPer100) == nil
        case .ev:
            return false
        }
    }

    static func needsEnergy(
        vehicle: VehicleCatalogItem,
        overrideKWhPer100: Double?
    ) -> Bool {
        switch vehicle.powertrain {
        case .ev, .phev:
            return resolvedEnergyKWhPerKm(vehicle: vehicle, overrideKWhPer100: overrideKWhPer100) == nil
        case .ice, .hev:
            return false
        }
    }

    static func needsRange(
        vehicle: VehicleCatalogItem,
        overrideKm: Double?
    ) -> Bool {
        guard vehicle.powertrain == .phev else { return false }
        return resolvedElectricRangeKm(vehicle: vehicle, overrideKm: overrideKm) == nil
    }

    // MARK: - Sufficiency (preview + verdict)

    static func overrides(for vehicle: VehicleCatalogItem, input: UserInput, asSource: Bool)
        -> (fuelLPer100: Double?, energyKWhPer100: Double?, rangeKm: Double?)
    {
        if asSource {
            return (
                input.sourceConsumptionOverrideLPer100Km,
                input.sourceEnergyOverrideKWhPer100Km,
                input.sourceElectricRangeOverrideKm
            )
        }
        return (
            input.targetFuelConsumptionOverrideLPer100Km,
            input.targetEnergyOverrideKWhPer100Km,
            input.targetElectricRangeOverrideKm
        )
    }

    /// Dati necessari presenti e validi per costi/verdetto (stessa regola del gate).
    static func hasSufficientCalcData(
        vehicle: VehicleCatalogItem,
        input: UserInput,
        asSource: Bool
    ) -> Bool {
        let o = overrides(for: vehicle, input: input, asSource: asSource)
        switch vehicle.powertrain {
        case .ice, .hev:
            return resolvedFuelLPerKm(vehicle: vehicle, overrideLPer100: o.fuelLPer100) != nil
        case .ev:
            return resolvedEnergyKWhPerKm(vehicle: vehicle, overrideKWhPer100: o.energyKWhPer100) != nil
        case .phev:
            return resolvedFuelLPerKm(vehicle: vehicle, overrideLPer100: o.fuelLPer100) != nil
                && resolvedEnergyKWhPerKm(vehicle: vehicle, overrideKWhPer100: o.energyKWhPer100) != nil
                && resolvedElectricRangeKm(vehicle: vehicle, overrideKm: o.rangeKm) != nil
        }
    }
}

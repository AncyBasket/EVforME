//
//  ScenarioLiveDelta.swift
//  EVforME?
//
//  Confronta prezzi/incentivi allo snapshot vs dati live (soglie retention 1.1).
//

import Foundation

enum ScenarioLiveDelta {
    static let fuelThresholdEURPerL: Double = 0.05
    static let electricityThresholdEURPerKWh: Double = 0.02
    static let incentiveThresholdEUR: Double = 100

    struct Report: Equatable {
        let fuelDelta: Double?
        let electricityDelta: Double?
        let incentiveDelta: Double?
        let previousSavingsMin: Int
        let previousSavingsMax: Int
        let currentSavingsMin: Int?
        let currentSavingsMax: Int?

        var fuelMoved: Bool {
            abs(fuelDelta ?? 0) >= fuelThresholdEURPerL
        }

        var electricityMoved: Bool {
            abs(electricityDelta ?? 0) >= electricityThresholdEURPerKWh
        }

        var incentiveMoved: Bool {
            abs(incentiveDelta ?? 0) >= incentiveThresholdEUR
        }

        var isMaterial: Bool {
            fuelMoved || electricityMoved || incentiveMoved
        }

        var savingsChanged: Bool {
            guard let curMin = currentSavingsMin, let curMax = currentSavingsMax else { return false }
            return curMin != previousSavingsMin || curMax != previousSavingsMax
        }
    }

    static func evaluate(
        snapshot: SavedScenarioSnapshot,
        liveFuel: Double,
        liveElectricity: Double,
        liveIncentiveEUR: Double,
        liveResult: SimulationResult?
    ) -> Report {
        let fuelDelta = snapshot.fuelPriceAtSave.map { liveFuel - $0 }
        let elecDelta = snapshot.electricityPriceAtSave.map { liveElectricity - $0 }
        let incentiveDelta = snapshot.incentiveEURAtSave.map { liveIncentiveEUR - $0 }
        return Report(
            fuelDelta: fuelDelta,
            electricityDelta: elecDelta,
            incentiveDelta: incentiveDelta,
            previousSavingsMin: snapshot.savingsMin,
            previousSavingsMax: snapshot.savingsMax,
            currentSavingsMin: liveResult.map { $0.yearlySavingsRange.lowerBound },
            currentSavingsMax: liveResult.map { $0.yearlySavingsRange.upperBound }
        )
    }

    /// True se i prezzi live si sono mossi oltre soglia rispetto allo snapshot (per reminder).
    static func liveDataMoved(versus snapshot: SavedScenarioSnapshot) -> Bool {
        let liveFuel = liveFuelPrice(fallback: snapshot.fuelPriceAtSave ?? snapshot.restoredUserInput().fuelPrice)
        let liveElec = liveElectricityPrice(
            fallback: snapshot.electricityPriceAtSave ?? snapshot.restoredUserInput().electricityPricePerKWh
        )
        let liveIncentive = snapshot.restoredUserInput().estimatedPurchaseIncentiveEUR
        let report = evaluate(
            snapshot: snapshot,
            liveFuel: liveFuel,
            liveElectricity: liveElec,
            liveIncentiveEUR: liveIncentive,
            liveResult: nil
        )
        return report.isMaterial
    }

    static func liveFuelPrice(fallback: Double) -> Double {
        if let cached = OfficialCostService.shared.cachedOrBundledCosts()?.fuelPricePerLiter {
            return cached
        }
        return fallback
    }

    static func liveElectricityPrice(fallback: Double) -> Double {
        if let cached = OfficialCostService.shared.cachedOrBundledCosts()?.electricityPricePerKWh {
            return cached
        }
        return fallback
    }
}

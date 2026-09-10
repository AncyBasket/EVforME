//
//  ScenarioHistoryStore.swift
//  EVforME?
//

import Foundation

/// Input completo serializzato per ripristinare uno scenario dallo storico.
struct PersistedScenarioInput: Codable, Equatable {
    var dailyKm: Int
    var hasHomeCharging: Bool
    var areaTypeRaw: Int
    var fuelPrice: Double
    var ownershipYears: Int
    var electricityPricePerKWh: Double
    var sourceVehicleId: String
    var targetVehicleId: String
    var scenarioRaw: Double
    var sourcePurchasePrice: Double
    var targetPurchasePrice: Double
    var includeIncentives: Bool
    var tripProfileRaw: String
    var sourceConsumptionOverrideLPer100Km: Double?
    var targetEnergyOverrideKWhPer100Km: Double?

    init(from input: UserInput) {
        dailyKm = input.dailyKm
        hasHomeCharging = input.hasHomeCharging
        areaTypeRaw = input.areaType == .urban ? 0 : 1
        fuelPrice = input.fuelPrice
        ownershipYears = input.ownershipYears
        electricityPricePerKWh = input.electricityPricePerKWh
        sourceVehicleId = input.sourceVehicleId
        targetVehicleId = input.targetVehicleId
        scenarioRaw = input.scenario.rawValue
        sourcePurchasePrice = input.sourcePurchasePrice
        targetPurchasePrice = input.targetPurchasePrice
        includeIncentives = input.includeIncentives
        tripProfileRaw = input.tripProfile.rawValue
        sourceConsumptionOverrideLPer100Km = input.sourceConsumptionOverrideLPer100Km
        targetEnergyOverrideKWhPer100Km = input.targetEnergyOverrideKWhPer100Km
    }

    func toUserInput() -> UserInput {
        let scenario = Scenario.allCases.first { $0.rawValue == scenarioRaw } ?? .realistic
        let trip = TripProfile(rawValue: tripProfileRaw) ?? .custom
        return UserInput(
            dailyKm: dailyKm,
            hasHomeCharging: hasHomeCharging,
            areaType: areaTypeRaw == 0 ? .urban : .mixed,
            fuelPrice: fuelPrice,
            ownershipYears: ownershipYears,
            electricityPricePerKWh: electricityPricePerKWh,
            sourceVehicleId: sourceVehicleId,
            targetVehicleId: targetVehicleId,
            scenario: scenario,
            sourcePurchasePrice: sourcePurchasePrice,
            targetPurchasePrice: targetPurchasePrice,
            includeIncentives: includeIncentives,
            tripProfile: trip,
            sourceConsumptionOverrideLPer100Km: sourceConsumptionOverrideLPer100Km,
            targetEnergyOverrideKWhPer100Km: targetEnergyOverrideKWhPer100Km
        )
    }
}

struct SavedScenarioSnapshot: Codable, Identifiable, Equatable {
    let id: UUID
    let createdAt: TimeInterval
    let verdictRaw: String
    let yearlyKm: Int
    let savingsMin: Int
    let savingsMax: Int
    let breakEvenMonths: Int?
    let hasHomeCharging: Bool
    let tripProfileRaw: String
    let scenarioRaw: Double
    let sourceVehicleId: String
    let targetVehicleId: String
    /// Presente dagli snapshot “v2”; se manca, il ripristino usa solo i campi legacy.
    let persistedInput: PersistedScenarioInput?

    var verdictTitle: String {
        (EVVerdict(rawValue: verdictRaw) ?? .maybe).title
    }

    var createdDate: Date { Date(timeIntervalSince1970: createdAt) }

    /// Ricostruisce l’input da ripristinare (full payload o fallback legacy).
    func restoredUserInput() -> UserInput {
        if let persistedInput {
            return persistedInput.toUserInput()
        }
        let scenario = Scenario.allCases.first { $0.rawValue == scenarioRaw } ?? .realistic
        let trip = TripProfile(rawValue: tripProfileRaw) ?? .custom
        return UserInput(
            dailyKm: yearlyKm,
            hasHomeCharging: hasHomeCharging,
            areaType: trip.suggestedAreaType,
            fuelPrice: 1.7,
            ownershipYears: 5,
            sourceVehicleId: sourceVehicleId,
            targetVehicleId: targetVehicleId,
            scenario: scenario,
            tripProfile: trip
        )
    }
}

enum ScenarioHistoryStore {
    private static let key = "evforme.scenarioHistory.v1"
    private static let maxItems = 8

    private static var defaults: UserDefaults { .standard }

    static func all() -> [SavedScenarioSnapshot] {
        guard let data = defaults.data(forKey: key),
              let decoded = try? JSONDecoder().decode([SavedScenarioSnapshot].self, from: data) else {
            return []
        }
        return decoded.sorted { $0.createdAt > $1.createdAt }
    }

    static func save(result: SimulationResult, input: UserInput) {
        var items = all()
        let snap = SavedScenarioSnapshot(
            id: UUID(),
            createdAt: Date().timeIntervalSince1970,
            verdictRaw: result.verdict.rawValue,
            yearlyKm: input.dailyKm,
            savingsMin: result.yearlySavingsRange.lowerBound,
            savingsMax: result.yearlySavingsRange.upperBound,
            breakEvenMonths: result.breakEvenMonths,
            hasHomeCharging: input.hasHomeCharging,
            tripProfileRaw: input.tripProfile.rawValue,
            scenarioRaw: input.scenario.rawValue,
            sourceVehicleId: input.sourceVehicleId,
            targetVehicleId: input.targetVehicleId,
            persistedInput: PersistedScenarioInput(from: input)
        )
        items.insert(snap, at: 0)
        if items.count > maxItems {
            items = Array(items.prefix(maxItems))
        }
        if let data = try? JSONEncoder().encode(items) {
            defaults.set(data, forKey: key)
        }
    }

    static func clear() {
        defaults.removeObject(forKey: key)
    }
}

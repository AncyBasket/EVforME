//
//  ScenarioHistoryStore.swift
//  EVforME?
//

import Foundation

/// Input completo serializzato per ripristinare uno scenario dallo storico.
struct PersistedScenarioInput: Equatable {
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
    var comparisonIntentRaw: String
    var tripProfileRaw: String
    var sourceConsumptionOverrideLPer100Km: Double?
    var targetEnergyOverrideKWhPer100Km: Double?
    var marketRaw: String?

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
        comparisonIntentRaw = input.comparisonIntent.rawValue
        tripProfileRaw = input.tripProfile.rawValue
        sourceConsumptionOverrideLPer100Km = input.sourceConsumptionOverrideLPer100Km
        targetEnergyOverrideKWhPer100Km = input.targetEnergyOverrideKWhPer100Km
        marketRaw = input.market.rawValue
    }

    func toUserInput() -> UserInput {
        let scenario = Scenario.allCases.first { $0.rawValue == scenarioRaw } ?? .realistic
        let trip = TripProfile(rawValue: tripProfileRaw) ?? .custom
        let intent = ComparisonIntent(rawValue: comparisonIntentRaw) ?? .alreadyOwned
        let market = marketRaw.flatMap(AppMarket.init(rawValue:)) ?? AppMarket.fromDeviceLocale()
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
            comparisonIntent: intent,
            tripProfile: trip,
            sourceConsumptionOverrideLPer100Km: sourceConsumptionOverrideLPer100Km,
            targetEnergyOverrideKWhPer100Km: targetEnergyOverrideKWhPer100Km,
            market: market
        )
    }
}

extension PersistedScenarioInput: Codable {
    private enum CodingKeys: String, CodingKey {
        case dailyKm, hasHomeCharging, areaTypeRaw, fuelPrice, ownershipYears
        case electricityPricePerKWh, sourceVehicleId, targetVehicleId, scenarioRaw
        case sourcePurchasePrice, targetPurchasePrice, includeIncentives
        case comparisonIntentRaw, tripProfileRaw
        case sourceConsumptionOverrideLPer100Km, targetEnergyOverrideKWhPer100Km
        case marketRaw
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        dailyKm = try c.decode(Int.self, forKey: .dailyKm)
        hasHomeCharging = try c.decode(Bool.self, forKey: .hasHomeCharging)
        areaTypeRaw = try c.decode(Int.self, forKey: .areaTypeRaw)
        fuelPrice = try c.decode(Double.self, forKey: .fuelPrice)
        ownershipYears = try c.decode(Int.self, forKey: .ownershipYears)
        electricityPricePerKWh = try c.decodeIfPresent(Double.self, forKey: .electricityPricePerKWh) ?? 0.25
        sourceVehicleId = try c.decode(String.self, forKey: .sourceVehicleId)
        targetVehicleId = try c.decode(String.self, forKey: .targetVehicleId)
        scenarioRaw = try c.decode(Double.self, forKey: .scenarioRaw)
        sourcePurchasePrice = try c.decodeIfPresent(Double.self, forKey: .sourcePurchasePrice) ?? 12_000
        targetPurchasePrice = try c.decodeIfPresent(Double.self, forKey: .targetPurchasePrice) ?? 32_000
        includeIncentives = try c.decodeIfPresent(Bool.self, forKey: .includeIncentives) ?? false
        comparisonIntentRaw = try c.decodeIfPresent(String.self, forKey: .comparisonIntentRaw)
            ?? ComparisonIntent.alreadyOwned.rawValue
        tripProfileRaw = try c.decodeIfPresent(String.self, forKey: .tripProfileRaw) ?? TripProfile.custom.rawValue
        sourceConsumptionOverrideLPer100Km = try c.decodeIfPresent(Double.self, forKey: .sourceConsumptionOverrideLPer100Km)
        targetEnergyOverrideKWhPer100Km = try c.decodeIfPresent(Double.self, forKey: .targetEnergyOverrideKWhPer100Km)
        marketRaw = try c.decodeIfPresent(String.self, forKey: .marketRaw)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(dailyKm, forKey: .dailyKm)
        try c.encode(hasHomeCharging, forKey: .hasHomeCharging)
        try c.encode(areaTypeRaw, forKey: .areaTypeRaw)
        try c.encode(fuelPrice, forKey: .fuelPrice)
        try c.encode(ownershipYears, forKey: .ownershipYears)
        try c.encode(electricityPricePerKWh, forKey: .electricityPricePerKWh)
        try c.encode(sourceVehicleId, forKey: .sourceVehicleId)
        try c.encode(targetVehicleId, forKey: .targetVehicleId)
        try c.encode(scenarioRaw, forKey: .scenarioRaw)
        try c.encode(sourcePurchasePrice, forKey: .sourcePurchasePrice)
        try c.encode(targetPurchasePrice, forKey: .targetPurchasePrice)
        try c.encode(includeIncentives, forKey: .includeIncentives)
        try c.encode(comparisonIntentRaw, forKey: .comparisonIntentRaw)
        try c.encode(tripProfileRaw, forKey: .tripProfileRaw)
        try c.encodeIfPresent(sourceConsumptionOverrideLPer100Km, forKey: .sourceConsumptionOverrideLPer100Km)
        try c.encodeIfPresent(targetEnergyOverrideKWhPer100Km, forKey: .targetEnergyOverrideKWhPer100Km)
        try c.encodeIfPresent(marketRaw, forKey: .marketRaw)
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

    // Retention 1.1 — opzionali per compatibilità con history già salvata.
    let sourceDisplayName: String?
    let targetDisplayName: String?
    let fuelPriceAtSave: Double?
    let electricityPriceAtSave: Double?
    let incentiveEURAtSave: Double?
    let energyUpdatedAtAtSave: String?
    let incentivesUpdatedAtAtSave: String?
    let incentivesValidUntilAtSave: String?

    var verdictTitle: String {
        (EVVerdict(rawValue: verdictRaw) ?? .maybe).title
    }

    var createdDate: Date { Date(timeIntervalSince1970: createdAt) }

    var pairLabel: String {
        let from = sourceDisplayName
            ?? VehicleCatalogService.shared.vehicle(by: sourceVehicleId)?.displayName
            ?? sourceVehicleId
        let to = targetDisplayName
            ?? VehicleCatalogService.shared.vehicle(by: targetVehicleId)?.displayName
            ?? targetVehicleId
        return "\(from) → \(to)"
    }

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
            fuelPrice: fuelPriceAtSave ?? 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: electricityPriceAtSave ?? 0.25,
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
    /// One-shot: flip legacy includeIncentives=true → false on saved comparisons.
    private static let includeIncentivesDefaultOffMigratedKey =
        "evforme.includeIncentives.defaultOff.history.v1"

    private static var defaults: UserDefaults { .standard }

    static func all() -> [SavedScenarioSnapshot] {
        guard let data = defaults.data(forKey: key),
              let decoded = try? JSONDecoder().decode([SavedScenarioSnapshot].self, from: data) else {
            return []
        }
        return decoded.sorted { $0.createdAt > $1.createdAt }
    }

    /// Once per install: persisted scenario inputs with `includeIncentives == true` → `false`.
    /// Prevents reopening an old comparison from re-enabling incentives after App Review honesty default.
    static func migrateIncludeIncentivesDefaultOffIfNeeded() {
        guard !defaults.bool(forKey: includeIncentivesDefaultOffMigratedKey) else { return }
        defaults.set(true, forKey: includeIncentivesDefaultOffMigratedKey)

        guard let data = defaults.data(forKey: key),
              let decoded = try? JSONDecoder().decode([SavedScenarioSnapshot].self, from: data) else {
            return
        }

        var changed = false
        let migrated: [SavedScenarioSnapshot] = decoded.map { snap in
            guard var persisted = snap.persistedInput, persisted.includeIncentives else {
                return snap
            }
            persisted.includeIncentives = false
            changed = true
            return SavedScenarioSnapshot(
                id: snap.id,
                createdAt: snap.createdAt,
                verdictRaw: snap.verdictRaw,
                yearlyKm: snap.yearlyKm,
                savingsMin: snap.savingsMin,
                savingsMax: snap.savingsMax,
                breakEvenMonths: snap.breakEvenMonths,
                hasHomeCharging: snap.hasHomeCharging,
                tripProfileRaw: snap.tripProfileRaw,
                scenarioRaw: snap.scenarioRaw,
                sourceVehicleId: snap.sourceVehicleId,
                targetVehicleId: snap.targetVehicleId,
                persistedInput: persisted,
                sourceDisplayName: snap.sourceDisplayName,
                targetDisplayName: snap.targetDisplayName,
                fuelPriceAtSave: snap.fuelPriceAtSave,
                electricityPriceAtSave: snap.electricityPriceAtSave,
                incentiveEURAtSave: 0,
                energyUpdatedAtAtSave: snap.energyUpdatedAtAtSave,
                incentivesUpdatedAtAtSave: snap.incentivesUpdatedAtAtSave,
                incentivesValidUntilAtSave: snap.incentivesValidUntilAtSave
            )
        }

        guard changed else { return }
        if let encoded = try? JSONEncoder().encode(migrated) {
            defaults.set(encoded, forKey: key)
        }
    }

    static func latest() -> SavedScenarioSnapshot? {
        all().first
    }

    static func save(result: SimulationResult, input: UserInput) {
        var items = all()
        let sourceName = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.displayName
        let targetName = VehicleCatalogService.shared.vehicle(by: input.targetVehicleId)?.displayName
        let costs = OfficialCostService.shared.cachedOrBundledCosts()
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
            persistedInput: PersistedScenarioInput(from: input),
            sourceDisplayName: sourceName,
            targetDisplayName: targetName,
            fuelPriceAtSave: input.fuelPrice,
            electricityPriceAtSave: input.electricityPricePerKWh,
            incentiveEURAtSave: input.estimatedPurchaseIncentiveEUR,
            energyUpdatedAtAtSave: costs?.updatedAt,
            incentivesUpdatedAtAtSave: ItalianIncentivesService.shared.currentSchedule.updatedAt,
            incentivesValidUntilAtSave: ItalianIncentivesService.shared.currentSchedule.validUntil
        )
        items.insert(snap, at: 0)
        if items.count > maxItems {
            items = Array(items.prefix(maxItems))
        }
        if let data = try? JSONEncoder().encode(items) {
            defaults.set(data, forKey: key)
        }
        RetentionReminderService.shared.armAfterVerdictSaved()
        NotificationCenter.default.post(name: .evScenarioHistoryDidChange, object: nil)
    }

    static func clear() {
        defaults.removeObject(forKey: key)
        NotificationCenter.default.post(name: .evScenarioHistoryDidChange, object: nil)
    }
}

extension Notification.Name {
    static let evScenarioHistoryDidChange = Notification.Name("evforme.scenarioHistory.didChange")
}

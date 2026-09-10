//
//  WidgetSnapshotStore.swift
//  EVforME?
//

import Foundation
import WidgetKit

/// Snapshot serializzato per Home Screen Widget (App Group).
struct VerdictWidgetSnapshot: Codable, Equatable {
    var verdictRaw: String
    var title: String
    var subtitle: String
    var yearlyKm: Int
    var savingsMin: Int
    var savingsMax: Int
    var weeklyCharges: Int
    var fuelPrice: Double
    /// Consumo ICE usato nell’ultima sim (L/100 km) per bump carburante realistico.
    var iceLPer100Km: Double
    var updatedAt: TimeInterval

    var verdict: EVVerdict {
        EVVerdict(rawValue: verdictRaw) ?? .maybe
    }

    enum CodingKeys: String, CodingKey {
        case verdictRaw, title, subtitle, yearlyKm, savingsMin, savingsMax
        case weeklyCharges, fuelPrice, iceLPer100Km, updatedAt
    }

    init(
        verdictRaw: String,
        title: String,
        subtitle: String,
        yearlyKm: Int,
        savingsMin: Int,
        savingsMax: Int,
        weeklyCharges: Int,
        fuelPrice: Double,
        iceLPer100Km: Double,
        updatedAt: TimeInterval
    ) {
        self.verdictRaw = verdictRaw
        self.title = title
        self.subtitle = subtitle
        self.yearlyKm = yearlyKm
        self.savingsMin = savingsMin
        self.savingsMax = savingsMax
        self.weeklyCharges = weeklyCharges
        self.fuelPrice = fuelPrice
        self.iceLPer100Km = iceLPer100Km
        self.updatedAt = updatedAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        verdictRaw = try c.decode(String.self, forKey: .verdictRaw)
        title = try c.decode(String.self, forKey: .title)
        subtitle = try c.decode(String.self, forKey: .subtitle)
        yearlyKm = try c.decode(Int.self, forKey: .yearlyKm)
        savingsMin = try c.decode(Int.self, forKey: .savingsMin)
        savingsMax = try c.decode(Int.self, forKey: .savingsMax)
        weeklyCharges = try c.decode(Int.self, forKey: .weeklyCharges)
        fuelPrice = try c.decodeIfPresent(Double.self, forKey: .fuelPrice) ?? 1.7
        iceLPer100Km = try c.decodeIfPresent(Double.self, forKey: .iceLPer100Km) ?? 7.0
        updatedAt = try c.decode(TimeInterval.self, forKey: .updatedAt)
    }
}

/// Input minimale condiviso app ↔ widget (per intent “benzina +€0.10”).
struct MirroredWidgetInput: Codable, Equatable {
    var fuelPrice: Double
    var dailyKm: Int
    var iceLPer100Km: Double

    enum CodingKeys: String, CodingKey {
        case fuelPrice, dailyKm, iceLPer100Km
    }

    init(fuelPrice: Double, dailyKm: Int, iceLPer100Km: Double) {
        self.fuelPrice = fuelPrice
        self.dailyKm = dailyKm
        self.iceLPer100Km = iceLPer100Km
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        fuelPrice = try c.decode(Double.self, forKey: .fuelPrice)
        dailyKm = try c.decode(Int.self, forKey: .dailyKm)
        iceLPer100Km = try c.decodeIfPresent(Double.self, forKey: .iceLPer100Km) ?? 7.0
    }
}

enum WidgetSnapshotStore {
    private static let key = "evforme.widget.verdictSnapshot"
    private static let inputKey = "evforme.widget.mirroredInput"
    static let fuelCustomizedKey = "evforme.autocosts.userCustomizedFuelPrice"

    private static var suite: UserDefaults {
        UserDefaults(suiteName: Defaults.appGroupID) ?? .standard
    }

    private static func resolveIceLPer100Km(from input: UserInput) -> Double {
        if let override = input.sourceConsumptionOverrideLPer100Km {
            return override
        }
        let catalog = VehicleCatalogService.shared
        if let vehicle = catalog.vehicle(by: input.sourceVehicleId),
           let lPerKm = vehicle.fuelConsumptionLPerKm {
            return lPerKm * 100.0
        }
        return 7.0
    }

    static func save(from result: SimulationResult, input: UserInput) {
        let ice = resolveIceLPer100Km(from: input)
        let snapshot = VerdictWidgetSnapshot(
            verdictRaw: result.verdict.rawValue,
            title: result.verdict.title,
            subtitle: result.verdict.description,
            yearlyKm: input.dailyKm,
            savingsMin: result.yearlySavingsRange.lowerBound,
            savingsMax: result.yearlySavingsRange.upperBound,
            weeklyCharges: result.weeklyCharges,
            fuelPrice: input.fuelPrice,
            iceLPer100Km: ice,
            updatedAt: Date().timeIntervalSince1970
        )
        if let data = try? JSONEncoder().encode(snapshot) {
            suite.set(data, forKey: key)
        }
        let mirror = MirroredWidgetInput(
            fuelPrice: input.fuelPrice,
            dailyKm: input.dailyKm,
            iceLPer100Km: ice
        )
        if let data = try? JSONEncoder().encode(mirror) {
            suite.set(data, forKey: inputKey)
        }
        WidgetCenter.shared.reloadAllTimelines()
    }

    static func load() -> VerdictWidgetSnapshot? {
        guard let data = suite.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(VerdictWidgetSnapshot.self, from: data)
    }

    static func loadMirroredUserInput() -> MirroredWidgetInput? {
        guard let data = suite.data(forKey: inputKey) else { return nil }
        return try? JSONDecoder().decode(MirroredWidgetInput.self, from: data)
    }
}

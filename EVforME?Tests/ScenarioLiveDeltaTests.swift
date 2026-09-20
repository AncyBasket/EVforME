//
//  ScenarioLiveDeltaTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class ScenarioLiveDeltaTests: XCTestCase {
    func testMaterialWhenFuelMovesBeyondThreshold() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000)
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.80,
            liveElectricity: 0.30,
            liveIncentiveEUR: 5000,
            liveResult: nil
        )
        XCTAssertTrue(report.fuelMoved)
        XCTAssertFalse(report.electricityMoved)
        XCTAssertTrue(report.isMaterial)
    }

    func testUnchangedWithinThreshold() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000)
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.73,
            liveElectricity: 0.31,
            liveIncentiveEUR: 5050,
            liveResult: nil
        )
        XCTAssertFalse(report.isMaterial)
    }

    func testIncentiveWindowChangeIsMaterial() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000, validUntil: "2026-06-30")
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.70,
            liveElectricity: 0.30,
            liveIncentiveEUR: 5000,
            liveResult: nil,
            liveValidUntil: "2026-12-31"
        )
        XCTAssertTrue(report.incentiveWindowChanged)
        XCTAssertTrue(report.isMaterial)
    }

    func testSameIncentiveWindowNotMaterial() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000, validUntil: "2026-12-31")
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.70,
            liveElectricity: 0.30,
            liveIncentiveEUR: 5000,
            liveResult: nil,
            liveValidUntil: "2026-12-31"
        )
        XCTAssertFalse(report.incentiveWindowChanged)
        XCTAssertFalse(report.isMaterial)
    }

    func testIncentiveWindowAppearingOnOldSnapshotIsNotMaterial() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000, validUntil: nil)
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.70,
            liveElectricity: 0.30,
            liveIncentiveEUR: 5000,
            liveResult: nil,
            liveValidUntil: "2026-12-31"
        )
        XCTAssertFalse(report.incentiveWindowChanged)
        XCTAssertFalse(report.isMaterial)
    }

    func testIncentiveWindowClearedIsMaterial() {
        let snap = makeSnapshot(fuel: 1.70, elec: 0.30, incentive: 5000, validUntil: "2026-12-31")
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snap,
            liveFuel: 1.70,
            liveElectricity: 0.30,
            liveIncentiveEUR: 5000,
            liveResult: nil,
            liveValidUntil: nil
        )
        XCTAssertTrue(report.incentiveWindowChanged)
        XCTAssertTrue(report.isMaterial)
    }

    private func makeSnapshot(
        fuel: Double,
        elec: Double,
        incentive: Double,
        validUntil: String? = nil
    ) -> SavedScenarioSnapshot {
        SavedScenarioSnapshot(
            id: UUID(),
            createdAt: Date().timeIntervalSince1970,
            verdictRaw: "maybe",
            yearlyKm: 12_000,
            savingsMin: 400,
            savingsMax: 800,
            breakEvenMonths: 24,
            hasHomeCharging: true,
            tripProfileRaw: TripProfile.custom.rawValue,
            scenarioRaw: Scenario.realistic.rawValue,
            sourceVehicleId: "alfa-romeo-147-2005",
            targetVehicleId: "audi-q4-e-tron-2017",
            persistedInput: nil,
            sourceDisplayName: "ICE",
            targetDisplayName: "EV",
            fuelPriceAtSave: fuel,
            electricityPriceAtSave: elec,
            incentiveEURAtSave: incentive,
            energyUpdatedAtAtSave: nil,
            incentivesUpdatedAtAtSave: nil,
            incentivesValidUntilAtSave: validUntil
        )
    }
}

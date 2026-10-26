//
//  CatalogVehicleIdResolverTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class CatalogVehicleIdResolverTests: XCTestCase {
    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        CatalogVehicleIdResolver.aliases = [:]
    }

    override func tearDown() {
        CatalogVehicleIdResolver.aliases = [:]
        super.tearDown()
    }

    func testRemovedCatalogIdFallsBackToStarterTarget() {
        let removed = "hyundai-equus-2025"
        XCTAssertNil(
            VehicleCatalogService.shared.vehicle(by: removed),
            "PR A must remove nonexistent Equus EV rows"
        )

        let resolved = CatalogVehicleIdResolver.resolveTargetId(removed)
        XCTAssertFalse(resolved.isEmpty)
        XCTAssertNotEqual(resolved, removed)
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: resolved))
        // Starter target still present on this seed (Model 3 2026 until PR B).
        if VehicleCatalogService.shared.vehicle(by: Defaults.starterTargetVehicleId) != nil {
            XCTAssertEqual(resolved, Defaults.starterTargetVehicleId)
        }
    }

    func testSanitizeUserInputRewritesRemovedIds() {
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: "nissan-altra-ev-2024",
            targetVehicleId: "lucid-gravity-2022",
            scenario: .realistic
        )
        let changed = CatalogVehicleIdResolver.sanitizeUserInput(&input)
        XCTAssertTrue(changed)
        XCTAssertNotEqual(input.sourceVehicleId, "nissan-altra-ev-2024")
        XCTAssertNotEqual(input.targetVehicleId, "lucid-gravity-2022")
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId))
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: input.targetVehicleId))
    }

    func testAliasRemapTakesPrecedence() {
        let aliasTarget = Defaults.starterTargetVehicleId
        guard VehicleCatalogService.shared.vehicle(by: aliasTarget) != nil else {
            XCTFail("starter target missing from bundled seed")
            return
        }
        CatalogVehicleIdResolver.aliases = ["gone-ev-2099": aliasTarget]
        XCTAssertEqual(
            CatalogVehicleIdResolver.resolveId("gone-ev-2099"),
            aliasTarget
        )
    }

    func testSimulateDoesNotCrashOnRemovedTargetId() {
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: "hyundai-equus-2026",
            scenario: .realistic
        )
        CatalogVehicleIdResolver.sanitizeUserInput(&input)
        let result = EVSimulator.simulate(input: input)
        XCTAssertNotNil(result, "Simulation must succeed after resolving removed catalog id")
    }

    func testSanitizeHistoryRestoreEmptiesUnavailableIds() {
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: "lexus-rz-2022",
            scenario: .realistic
        )
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: "lexus-rz-2022"))
        XCTAssertTrue(CatalogVehicleIdResolver.isUnavailable("lexus-rz-2022"))
        let changed = CatalogVehicleIdResolver.sanitizeUserInput(&input, fallbackToStarter: false)
        XCTAssertTrue(changed)
        XCTAssertEqual(input.sourceVehicleId, Defaults.starterSourceVehicleId)
        XCTAssertTrue(input.targetVehicleId.isEmpty, "Removed id must not silently become another EV")
    }

    func testHistoryLabelMarksUnavailableVehicle() {
        let label = CatalogVehicleIdResolver.historyLabel(
            rawId: "hyundai-equus-2025",
            savedDisplayName: "Hyundai Equus EV 2025"
        )
        XCTAssertTrue(
            label.contains("non più in catalogo") || label.contains("no longer in catalog"),
            "History must not present a removed name as still valid: \(label)"
        )
    }

    func testRestoredUserInputEmptiesRemovedTargetAndKeepsLabelHonest() {
        let sourceId = Defaults.starterSourceVehicleId
        guard let source = VehicleCatalogService.shared.vehicle(by: sourceId) else {
            XCTFail("starter source missing")
            return
        }
        let removedTarget = "lexus-rz-2022"
        var persisted = PersistedScenarioInput(from: UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: sourceId,
            targetVehicleId: removedTarget,
            scenario: .realistic
        ))
        persisted.targetVehicleId = removedTarget
        let snap = SavedScenarioSnapshot(
            id: UUID(),
            createdAt: Date().timeIntervalSince1970,
            verdictRaw: EVVerdict.maybe.rawValue,
            yearlyKm: 12_000,
            savingsMin: 100,
            savingsMax: 200,
            breakEvenMonths: 24,
            hasHomeCharging: true,
            tripProfileRaw: TripProfile.custom.rawValue,
            scenarioRaw: Scenario.realistic.rawValue,
            sourceVehicleId: sourceId,
            targetVehicleId: removedTarget,
            persistedInput: persisted,
            sourceDisplayName: source.displayName,
            targetDisplayName: "Lexus RZ 2022",
            fuelPriceAtSave: 1.8,
            electricityPriceAtSave: 0.31,
            incentiveEURAtSave: 0,
            energyUpdatedAtAtSave: nil,
            incentivesUpdatedAtAtSave: nil,
            incentivesValidUntilAtSave: nil,
            bolloPartial: false
        )

        XCTAssertTrue(snap.hasUnavailableCatalogVehicle)
        let restored = snap.restoredUserInput()
        XCTAssertEqual(restored.sourceVehicleId, sourceId)
        XCTAssertTrue(restored.targetVehicleId.isEmpty)
        XCTAssertTrue(
            snap.pairLabel.contains("non più in catalogo")
                || snap.pairLabel.contains("no longer in catalog")
        )
        // Re-open / recalculate path: never simulate another car under the stale label.
        XCTAssertNil(
            VehicleCatalogService.shared.vehicle(by: removedTarget)
        )
        XCTAssertFalse(ScenarioLiveDelta.liveDataMoved(versus: snap))
    }

    func testKeptSoulAndNioEl8Present_RemovedRz2022Absent() {
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: "kia-soul-ev-2024"))
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: "kia-soul-ev-2025"))
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: "nio-el8-2022"))
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: "lexus-rz-2022"))
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: "volvo-c40-recharge-2025"))
        XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: "volvo-xc40-recharge-2025"))
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: "volvo-c40-recharge-2026"))
    }
}

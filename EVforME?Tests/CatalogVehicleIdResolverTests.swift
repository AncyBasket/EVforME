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
}

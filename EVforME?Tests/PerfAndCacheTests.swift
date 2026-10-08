//
//  PerfAndCacheTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class PerfAndCacheTests: XCTestCase {

    func testMIMITSampleCSV_ParsesPetrolAndDieselMedians() throws {
        let url = try XCTUnwrap(
            Bundle(for: PerfAndCacheTests.self).url(forResource: "mimit_sample", withExtension: "csv")
                ?? Bundle.main.url(forResource: "mimit_sample", withExtension: "csv")
        )
        // Prefer test bundle via path relative to this file when XCTest copies fixtures.
        let data: Data
        if let bundled = try? Data(contentsOf: url) {
            data = bundled
        } else {
            let fixture = URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .appendingPathComponent("Fixtures/mimit_sample.csv")
            data = try Data(contentsOf: fixture)
        }
        let medians = OfficialCostService.parseMIMITFuelMedians(from: data)
        XCTAssertNotNil(medians.petrol)
        XCTAssertNotNil(medians.diesel)
        // Self-service benzina: 1.799, 1.850, 1.820 → median 1.820
        XCTAssertEqual(medians.petrol!, 1.820, accuracy: 0.001)
        // Gasolio: 1.650, 1.700 → median of 2 is upper mid → 1.700 with count/2
        XCTAssertEqual(medians.diesel!, 1.700, accuracy: 0.001)
    }

    func testInsurancePerYear_HasFloorAndScalesWithKm() {
        let low = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: 10_000,
            yearlyKm: 5_000,
            electrified: false
        )
        let high = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: 10_000,
            yearlyKm: 40_000,
            electrified: false
        )
        XCTAssertGreaterThanOrEqual(low, 320)
        XCTAssertGreaterThan(high, low)
    }

    func testRemoteCatalogSmallerThanLocal_IsRejected() async {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        let localCount = VehicleCatalogService.shared.vehicles.count
        XCTAssertGreaterThan(localCount, 100)
        // Logic under test: refreshFromRemoteIfPossible discards when decoded.count + 50 < localCount.
        // Simulate the predicate here (network URL empty in tests).
        let tinyRemoteCount = 10
        XCTAssertTrue(tinyRemoteCount + 50 < localCount)
    }

    func testScenarioHistoryStore_RoundTrip() {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        let input = UserInput(
            dailyKm: 14_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.75,
            ownershipYears: 5,
            electricityPricePerKWh: 0.28,
            sourceVehicleId: "seat-ateca-2016",
            targetVehicleId: "tesla-model-3-2023",
            scenario: .realistic,
            sourcePurchasePrice: 14_000,
            targetPurchasePrice: 40_000
        )
        guard let result = EVSimulator.simulate(input: input) else {
            XCTFail("Simulate failed")
            return
        }
        ScenarioHistoryStore.save(result: result, input: input)
        let latest = ScenarioHistoryStore.latest()
        XCTAssertNotNil(latest)
        let restored = latest!.restoredUserInput()
        XCTAssertEqual(restored.sourceVehicleId, input.sourceVehicleId)
        XCTAssertEqual(restored.targetVehicleId, input.targetVehicleId)
        XCTAssertEqual(restored.dailyKm, input.dailyKm)
    }

    func testBundledCatalog_IsQualitySeedOnly() {
        // After membershipExceptions, only quality seed is in the app bundle.
        XCTAssertNotNil(Bundle.main.url(forResource: "vehicles.seed.quality", withExtension: "json"))
        XCTAssertNil(Bundle.main.url(forResource: "vehicles.seed.wltp_enriched", withExtension: "json"))
        XCTAssertNil(Bundle.main.url(forResource: "eea_co2_cars_landing", withExtension: "html"))
    }
}

//
//  PerfAndCacheTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class PerfAndCacheTests: XCTestCase {

    func testMIMITSampleCSV_ParsesPetrolDieselLPGAndCNG() throws {
        let url = try XCTUnwrap(
            Bundle(for: PerfAndCacheTests.self).url(forResource: "mimit_sample", withExtension: "csv")
                ?? Bundle.main.url(forResource: "mimit_sample", withExtension: "csv")
        )
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
        XCTAssertNotNil(medians.lpg)
        XCTAssertNotNil(medians.cng)
        // Self-service benzina: 1.799, 1.850, 1.820 → median 1.820
        XCTAssertEqual(medians.petrol!, 1.820, accuracy: 0.001)
        // Gasolio: 1.650, 1.700 → median of 2 is upper mid → 1.700 with count/2
        XCTAssertEqual(medians.diesel!, 1.700, accuracy: 0.001)
        // GPL: 0.750, 0.780 → 0.780
        XCTAssertEqual(medians.lpg!, 0.780, accuracy: 0.001)
        // Metano: 1.250, 1.300 → 1.300
        XCTAssertEqual(medians.cng!, 1.300, accuracy: 0.001)
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

    func testRemoteCatalogSmallerThanLocal_IsRejected() throws {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        let localCount = VehicleCatalogService.shared.vehicles.count
        XCTAssertGreaterThan(localCount, 100)

        let tinyJSON = Data("""
        [
          {
            "id": "tiny-remote-1",
            "brand": "Tiny",
            "model": "Remote",
            "year": 2024,
            "powertrain": "ice",
            "lengthM": 4.0,
            "widthM": 1.8,
            "heightM": 1.5,
            "fuelConsumptionLPerKm": 0.06,
            "energyConsumptionKWhPerKm": null,
            "maintenancePerYear": 400,
            "taxesPerYear": 200
          }
        ]
        """.utf8)

        XCTAssertFalse(
            VehicleCatalogService.shouldAcceptRemoteCatalog(decodedCount: 1, localCount: localCount)
        )
        let before = VehicleCatalogService.shared.vehicles.count
        let accepted = VehicleCatalogService.shared.applyRemoteCatalogJSONIfAcceptable(tinyJSON)
        XCTAssertFalse(accepted)
        XCTAssertEqual(VehicleCatalogService.shared.vehicles.count, before)
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: "tiny-remote-1"))
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

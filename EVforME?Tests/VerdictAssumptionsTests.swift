//
//  VerdictAssumptionsTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class VerdictAssumptionsTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    func testSnapshot_UsesOverridesAndSliderPrices() {
        var input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.93,
            ownershipYears: 5,
            electricityPricePerKWh: 0.27,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023"
        )
        input.sourceConsumptionOverrideLPer100Km = 7.4
        input.targetEnergyOverrideKWhPer100Km = 15.5

        let snap = VerdictAssumptions.snapshot(userInput: input)
        XCTAssertEqual(snap.sourceLPer100Km ?? -1, 7.4, accuracy: 0.001)
        XCTAssertEqual(snap.targetKWhPer100Km ?? -1, 15.5, accuracy: 0.001)
        XCTAssertEqual(snap.fuelPricePerLiter, 1.93, accuracy: 0.001)
        XCTAssertEqual(snap.electricityPricePerKWh, 0.27, accuracy: 0.001)

        let fuelLine = VerdictAssumptions.fuelPriceLine(from: snap)
        let elecLine = VerdictAssumptions.electricityLine(from: snap)
        XCTAssertTrue(fuelLine.contains("1") || fuelLine.contains("€"), fuelLine)
        XCTAssertTrue(elecLine.contains("0") || elecLine.contains("€"), elecLine)
        XCTAssertFalse(fuelLine.localizedCaseInsensitiveContains("6,5"))
        XCTAssertFalse(elecLine.localizedCaseInsensitiveContains("0,25"))
    }

    func testSnapshot_FallsBackToCatalogConsumption() {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.80,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023"
        )
        let snap = VerdictAssumptions.snapshot(userInput: input)
        let source = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)
        let target = VehicleCatalogService.shared.vehicle(by: input.targetVehicleId)
        if let lPerKm = source?.fuelConsumptionLPerKm, lPerKm > 0 {
            XCTAssertEqual(snap.sourceLPer100Km ?? -1, lPerKm * 100, accuracy: 0.05)
        }
        if let kWhPerKm = target?.resolvedEnergyKWhPerKm, kWhPerKm > 0 {
            XCTAssertEqual(snap.targetKWhPer100Km ?? -1, kWhPerKm * 100, accuracy: 0.05)
        }
        XCTAssertEqual(snap.fuelPricePerLiter, 1.80, accuracy: 0.001)
        XCTAssertEqual(snap.electricityPricePerKWh, 0.31, accuracy: 0.001)
    }
}

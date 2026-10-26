//
//  EVVariantsTests.swift
//  EVforME?Tests
//
//  Seed v59: EEA version rows, single-child aliases, no silent multi remap.
//

import XCTest
@testable import EVforME_

final class EVVariantsTests: XCTestCase {
    private let multiParent = "bmw-i4-2024"
    private let multiChild = "bmw-i4-2024-v105kw-591km"
    private let singleParent = "audi-q8-e-tron-2024"
    private let singleChild = "audi-q8-e-tron-2024-v300kw-530km"
    private let inputKey = "evforme.lastUserInput"

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        CatalogVehicleIdResolver.resetAliasesForTesting()
        UserDefaults.standard.removeObject(forKey: inputKey)
        ErrorHandler.shared.clearRecentErrorsForTesting()
    }

    override func tearDown() {
        CatalogVehicleIdResolver.resetAliasesForTesting()
        UserDefaults.standard.removeObject(forKey: inputKey)
        super.tearDown()
    }

    func testVersionChildHasParentIdRangePowerAndEnergy() {
        guard let child = VehicleCatalogService.shared.vehicle(by: multiChild) else {
            XCTFail("missing multi child \(multiChild)")
            return
        }
        XCTAssertEqual(child.parentId, multiParent)
        XCTAssertEqual(child.wltpRangeKm, 591)
        XCTAssertEqual(child.powerKw ?? 0, 105, accuracy: 0.6)
        XCTAssertNotNil(child.resolvedEnergyKWhPerKm)
        XCTAssertTrue(child.trim?.contains("km WLTP") == true)
        XCTAssertNil(child.batteryKWh, "new EEA versions must not invent battery")
    }

    func testMultiParentKeepsNoRangeAndNeedsExplicitChoice() {
        guard let parent = VehicleCatalogService.shared.vehicle(by: multiParent) else {
            XCTFail("missing multi parent")
            return
        }
        XCTAssertNil(parent.parentId)
        XCTAssertTrue(parent.wltpRangeKm == nil || parent.wltpRangeKm == 0)
        XCTAssertTrue(CatalogVehicleIdResolver.needsExplicitVersionChoice(multiParent))
        XCTAssertEqual(CatalogVehicleIdResolver.resolveId(multiParent), multiParent)
    }

    func testSingleVersionAliasRemapsWithoutSilentWrongCar() {
        XCTAssertEqual(
            CatalogVehicleIdResolver.resolveId(singleParent),
            singleChild
        )
        XCTAssertFalse(CatalogVehicleIdResolver.needsExplicitVersionChoice(singleParent))
        guard let child = VehicleCatalogService.shared.vehicle(by: singleChild) else {
            XCTFail("missing single child")
            return
        }
        XCTAssertEqual(child.wltpRangeKm, 530)
    }

    func testWeeklyChargesUseChosenVersionRange() {
        guard let child = VehicleCatalogService.shared.vehicle(by: multiChild),
              let range = child.wltpRangeKm else {
            XCTFail("child range missing")
            return
        }
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 12_000,
            powertrain: .ev,
            rangeKm: range,
            electricKmShare: 1
        )
        XCTAssertNotNil(charges)
        XCTAssertGreaterThan(charges ?? 0, 0)

        let without = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 12_000,
            powertrain: .ev,
            rangeKm: nil,
            electricKmShare: 1
        )
        XCTAssertNil(without)
    }

    func testSimulateOnMultiParentHasNilCharges_NoSilentVersion() {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: multiParent,
            scenario: .realistic
        )
        guard let result = EVSimulator.simulate(input: input) else {
            XCTFail("simulate should still run on parent (costs without range)")
            return
        }
        XCTAssertNil(result.weeklyCharges, "must not invent charges from another version")
    }

    func testSimulateOnChosenVersionShowsCharges() {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: multiChild,
            scenario: .realistic
        )
        guard let result = EVSimulator.simulate(input: input) else {
            XCTFail("simulate failed")
            return
        }
        XCTAssertNotNil(result.weeklyCharges)
        XCTAssertGreaterThan(result.weeklyCharges ?? 0, 0)
    }

    func testLoadPersistedMultiParentDoesNotRemapToRandomChild() {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: multiParent,
            scenario: .realistic
        )
        StorageService.shared.saveUserInput(input)
        guard let loaded = StorageService.shared.loadLastUserInput() else {
            XCTFail("load failed")
            return
        }
        XCTAssertEqual(loaded.targetVehicleId, multiParent)
        XCTAssertNotEqual(loaded.targetVehicleId, multiChild)
        XCTAssertTrue(CatalogVehicleIdResolver.needsExplicitVersionChoice(loaded.targetVehicleId))
    }

    func testTeslaModel3_2026OfficialTrimsUntouched() {
        let ids = [
            "tesla-model-3-trazione-posteriore-2026",
            "tesla-model-3-premium-trazione-posteriore-2026",
            "tesla-model-3-premium-long-range-2026",
            "tesla-model-3-performance-2026",
        ]
        for id in ids {
            guard let v = VehicleCatalogService.shared.vehicle(by: id) else {
                XCTFail("missing \(id)")
                return
            }
            XCTAssertNil(v.parentId)
            XCTAssertNotNil(v.wltpRangeKm)
            XCTAssertFalse(v.trim?.contains("km WLTP") == true, "official IT name, not EEA label")
        }
    }

    func testChargingNoteAsksForVersionWhenNeeded() {
        let note = L10n.calculationChargingNote(nil, needsVersionChoice: true)
        XCTAssertTrue(
            note.localizedCaseInsensitiveContains("version")
                || note.localizedCaseInsensitiveContains("versione")
        )
    }
}

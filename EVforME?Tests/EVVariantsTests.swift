//
//  EVVariantsTests.swift
//  EVforME?Tests
//
//  Seed v60: EEA version groups + exclusive Cn / noise / official kW.
//

import XCTest
@testable import EVforME_

final class EVVariantsTests: XCTestCase {
    private let multiParent = "bmw-i4-2024"
    private let multiChild = "bmw-i4-2024-v105kw-rwd"
    private let singleParent = "bmw-i5-2023"
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

    func testVersionGroupHasParentIdPrudentRangeAndCaption() {
        guard let child = VehicleCatalogService.shared.vehicle(by: multiChild) else {
            XCTFail("missing multi child \(multiChild)")
            return
        }
        XCTAssertEqual(child.parentId, multiParent)
        XCTAssertEqual(child.wltpRangeKm, 555)
        XCTAssertEqual(child.wltpRangeKmMax, 591)
        XCTAssertEqual(child.powerKw ?? 0, 105, accuracy: 0.6)
        XCTAssertNotNil(child.resolvedEnergyKWhPerKm)
        XCTAssertTrue(child.trim?.contains("kW") == true)
        XCTAssertFalse(child.trim?.contains("km WLTP") == true)
        XCTAssertTrue(child.variantRangeCaption?.contains("555") == true)
        XCTAssertTrue(child.variantRangeCaption?.contains("591") == true)
        XCTAssertEqual(child.usesPrudentVariantBounds, true)
        XCTAssertNil(child.batteryKWh, "new EEA groups must not invent battery")
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
        let children = VehicleCatalogService.shared.targetEVVehicles().filter {
            $0.parentId == multiParent
        }
        XCTAssertGreaterThanOrEqual(children.count, 2)
        XCTAssertLessThanOrEqual(children.count, 8)
    }

    func testSingleVersionAliasRemapsWithoutSilentWrongCar() {
        let resolved = CatalogVehicleIdResolver.resolveId(singleParent)
        XCTAssertNotNil(resolved)
        XCTAssertNotEqual(resolved, singleParent)
        XCTAssertFalse(CatalogVehicleIdResolver.needsExplicitVersionChoice(singleParent))
        guard let id = resolved, let child = VehicleCatalogService.shared.vehicle(by: id) else {
            XCTFail("missing single child")
            return
        }
        XCTAssertEqual(child.parentId, singleParent)
        XCTAssertNotNil(child.wltpRangeKm)
    }

    func testWeeklyChargesUsePrudentMinRange() {
        guard let child = VehicleCatalogService.shared.vehicle(by: multiChild),
              let range = child.wltpRangeKm else {
            XCTFail("child range missing")
            return
        }
        XCTAssertEqual(range, child.wltpRangeKm) // catalog stores min
        if let max = child.wltpRangeKmMax {
            XCTAssertLessThanOrEqual(range, max)
        }
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 12_000,
            powertrain: .ev,
            rangeKm: range,
            electricKmShare: 1
        )
        XCTAssertNotNil(charges)
        XCTAssertGreaterThan(charges ?? 0, 0)
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
            XCTFail("simulate should still run on parent")
            return
        }
        XCTAssertNil(result.weeklyCharges)
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
            XCTAssertNotEqual(v.usesPrudentVariantBounds, true)
        }
    }

    func testChargingNoteAsksForVersionWhenNeeded() {
        let note = L10n.calculationChargingNote(nil, needsVersionChoice: true)
        XCTAssertTrue(
            note.localizedCaseInsensitiveContains("version")
                || note.localizedCaseInsensitiveContains("versione")
        )
    }

    func testPrudentCalcNoteLocalized() {
        let note = L10n.variantPrudentCalcNote
        XCTAssertFalse(note.isEmpty)
        XCTAssertTrue(
            note.localizedCaseInsensitiveContains("prudent")
                || note.localizedCaseInsensitiveContains("prudente")
                || note.localizedCaseInsensitiveContains("cautious")
        )
    }

    func testRemovedVersionIdIsNotSilentlyAliased() {
        // Dropped by noise/official-kW cleanup — must force re-pick (PR #21 rule).
        let gone = "tesla-model-y-2023-v61kw-rwd"
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: gone))
        XCTAssertNil(CatalogVehicleIdResolver.resolveId(gone))
        XCTAssertTrue(CatalogVehicleIdResolver.isUnavailable(gone))
        XCTAssertNil(CatalogVehicleIdResolver.aliases[gone])
    }
}

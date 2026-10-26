//
//  RemovedCatalogIdSafetyTests.swift
//  EVforME?Tests
//
//  Removed / empty catalog ids must never silently become Golf/Model 3 numbers.
//

import XCTest
@testable import EVforME_

final class RemovedCatalogIdSafetyTests: XCTestCase {
    private let removedTarget = "lexus-rz-2022"
    private let historyKey = "evforme.scenarioHistory.v1"
    private let inputKey = "evforme.lastUserInput"

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        CatalogVehicleIdResolver.resetAliasesForTesting()
        ScenarioHistoryStore.clear()
        UserDefaults.standard.removeObject(forKey: inputKey)
        ErrorHandler.shared.clearRecentErrorsForTesting()
    }

    override func tearDown() {
        ScenarioHistoryStore.clear()
        UserDefaults.standard.removeObject(forKey: inputKey)
        CatalogVehicleIdResolver.resetAliasesForTesting()
        super.tearDown()
    }

    // MARK: - EVSimulator

    func testSimulateReturnsNilForEmptyVehicleIds() {
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: "",
            targetVehicleId: "",
            scenario: .realistic
        )
        XCTAssertNil(EVSimulator.simulate(input: input))
        input.sourceVehicleId = Defaults.starterSourceVehicleId
        input.targetVehicleId = ""
        XCTAssertNil(EVSimulator.simulate(input: input))
        input.sourceVehicleId = ""
        input.targetVehicleId = Defaults.starterTargetVehicleId
        XCTAssertNil(EVSimulator.simulate(input: input))
    }

    func testSimulateReturnsNilForRemovedCatalogIdWithoutSanitize() {
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: removedTarget))
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: removedTarget,
            scenario: .realistic
        )
        XCTAssertNil(
            EVSimulator.simulate(input: input),
            "Must not fall back to starter Model 3 under a removed id"
        )
    }

    func testSimulateValidIds_LabelAndNumbersAreSameCar() {
        let sourceId = Defaults.starterSourceVehicleId
        let targetId = Defaults.starterTargetVehicleId
        guard let source = VehicleCatalogService.shared.vehicle(by: sourceId),
              let target = VehicleCatalogService.shared.vehicle(by: targetId) else {
            XCTFail("starter vehicles missing")
            return
        }
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: sourceId,
            targetVehicleId: targetId,
            scenario: .realistic
        )
        guard let result = EVSimulator.simulate(input: input) else {
            XCTFail("simulate should succeed for live ids")
            return
        }
        let switchReason = result.keyReasons.first { $0.contains(source.displayName) && $0.contains(target.displayName) }
        XCTAssertNotNil(
            switchReason,
            "Result reasons must name the same cars as the catalog labels: \(result.keyReasons)"
        )
        let historyLabel = CatalogVehicleIdResolver.historyLabel(
            rawId: targetId,
            savedDisplayName: target.displayName
        )
        XCTAssertEqual(historyLabel, target.displayName)
        XCTAssertFalse(historyLabel.contains("non più in catalogo"))
        XCTAssertFalse(historyLabel.contains("no longer in catalog"))
    }

    // MARK: - Storage load

    func testLoadLastUserInput_RemovedIdWarnsAndDoesNotSilentSwap() {
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: removedTarget))
        let payload: [String: Any] = [
            "dailyKm": 12_000,
            "hasHomeCharging": true,
            "areaTypeRaw": 0,
            "fuelPrice": 1.8,
            "ownershipYears": 5,
            "electricityPricePerKWh": 0.31,
            "sourceVehicleId": Defaults.starterSourceVehicleId,
            "targetVehicleId": removedTarget,
            "scenarioRaw": Scenario.realistic.rawValue,
            "sourcePurchasePrice": 12_000.0,
            "targetPurchasePrice": 32_000.0,
            "includeIncentives": false,
            "comparisonIntentRaw": ComparisonIntent.alreadyOwned.rawValue,
            "tripProfileRaw": TripProfile.custom.rawValue,
            "includeKaskoTheft": false
        ]
        UserDefaults.standard.set(try! JSONSerialization.data(withJSONObject: payload), forKey: inputKey)

        let exp = expectation(description: "catalog warning")
        let token = NotificationCenter.default.addObserver(
            forName: .errorOccurred,
            object: nil,
            queue: .main
        ) { note in
            guard let n = note.userInfo?["notification"] as? ErrorNotification else { return }
            if n.context == .catalog, n.userMessage == L10n.catalogVehiclePickAnother {
                exp.fulfill()
            }
        }
        defer { NotificationCenter.default.removeObserver(token) }

        let loaded = StorageService.shared.loadLastUserInput()
        wait(for: [exp], timeout: 2.0)

        XCTAssertNotNil(loaded)
        XCTAssertEqual(loaded?.sourceVehicleId, Defaults.starterSourceVehicleId)
        XCTAssertTrue(
            loaded?.targetVehicleId.isEmpty == true,
            "Removed id must become empty — not the starter EV"
        )
        XCTAssertNotEqual(loaded?.targetVehicleId, Defaults.starterTargetVehicleId)
        XCTAssertNil(EVSimulator.simulate(input: loaded!))
        XCTAssertFalse(
            ErrorHandler.shared.recentErrorsForTesting().filter { $0.context == .catalog }.isEmpty
        )
    }

    // MARK: - History reopen / recalculate path

    func testHistoryRestoreRemovedId_NoResultNoWidgetNoSave() {
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: removedTarget))

        let goodInput = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            scenario: .realistic
        )
        StorageService.shared.saveUserInput(goodInput)
        guard let goodResult = EVSimulator.simulate(input: goodInput) else {
            XCTFail("baseline simulate failed")
            return
        }
        WidgetSnapshotStore.save(from: goodResult, input: goodInput)
        let widgetBefore = WidgetSnapshotStore.load()?.updatedAt
        let savedBefore = StorageService.shared.loadLastUserInput()?.targetVehicleId

        var persisted = PersistedScenarioInput(from: goodInput)
        persisted.targetVehicleId = removedTarget
        let snap = SavedScenarioSnapshot(
            id: UUID(),
            createdAt: Date().timeIntervalSince1970,
            verdictRaw: goodResult.verdict.rawValue,
            yearlyKm: 12_000,
            savingsMin: goodResult.yearlySavingsRange.lowerBound,
            savingsMax: goodResult.yearlySavingsRange.upperBound,
            breakEvenMonths: goodResult.breakEvenMonths,
            hasHomeCharging: true,
            tripProfileRaw: TripProfile.custom.rawValue,
            scenarioRaw: Scenario.realistic.rawValue,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: removedTarget,
            persistedInput: persisted,
            sourceDisplayName: "ICE",
            targetDisplayName: "Lexus RZ 2022",
            fuelPriceAtSave: 1.8,
            electricityPriceAtSave: 0.31,
            incentiveEURAtSave: 0,
            energyUpdatedAtAtSave: nil,
            incentivesUpdatedAtAtSave: nil,
            incentivesValidUntilAtSave: nil,
            bolloPartial: false
        )
        if let data = try? JSONEncoder().encode([snap]) {
            UserDefaults.standard.set(data, forKey: historyKey)
        }

        XCTAssertTrue(snap.hasUnavailableCatalogVehicle)

        // Reopen / recalculate contract: check first — no mutate save / widget / simulate.
        XCTAssertNil(EVSimulator.simulate(input: snap.restoredUserInput()))
        XCTAssertEqual(
            StorageService.shared.loadLastUserInput()?.targetVehicleId,
            savedBefore,
            "Must not overwrite last input when restore is refused"
        )
        XCTAssertEqual(
            WidgetSnapshotStore.load()?.updatedAt,
            widgetBefore,
            "Must not write widget on failed restore"
        )
        XCTAssertTrue(
            snap.pairLabel.contains("non più in catalogo")
                || snap.pairLabel.contains("no longer in catalog")
        )
    }

    // MARK: - App Intent (Shortcuts / Siri)

    @MainActor
    func testSimulateEVIntent_RemovedSavedId_NoStarterNoSimulateNoPersist() {
        XCTAssertNil(VehicleCatalogService.shared.vehicle(by: removedTarget))

        let goodInput = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            scenario: .realistic
        )
        StorageService.shared.saveUserInput(goodInput)
        guard let goodResult = EVSimulator.simulate(input: goodInput) else {
            XCTFail("baseline simulate failed")
            return
        }
        WidgetSnapshotStore.save(from: goodResult, input: goodInput)
        ScenarioHistoryStore.save(result: goodResult, input: goodInput)
        let widgetBefore = WidgetSnapshotStore.load()?.updatedAt
        let historyBefore = ScenarioHistoryStore.all().count

        // Persist a removed EV id the way a prior install would have left it.
        let payload: [String: Any] = [
            "dailyKm": 12_000,
            "hasHomeCharging": true,
            "areaTypeRaw": 0,
            "fuelPrice": 1.8,
            "ownershipYears": 5,
            "electricityPricePerKWh": 0.31,
            "sourceVehicleId": Defaults.starterSourceVehicleId,
            "targetVehicleId": removedTarget,
            "scenarioRaw": Scenario.realistic.rawValue,
            "sourcePurchasePrice": 12_000.0,
            "targetPurchasePrice": 32_000.0,
            "includeIncentives": false,
            "comparisonIntentRaw": ComparisonIntent.alreadyOwned.rawValue,
            "tripProfileRaw": TripProfile.custom.rawValue,
            "includeKaskoTheft": false
        ]
        UserDefaults.standard.set(try! JSONSerialization.data(withJSONObject: payload), forKey: inputKey)

        let outcome = SimulateEVIntentRunner.run(yearlyKm: 15_000, hasHomeCharging: false)

        XCTAssertFalse(outcome.didSimulate)
        XCTAssertEqual(outcome.message, L10n.catalogVehiclePickAnother)
        XCTAssertTrue(
            outcome.message.contains("catalogo") || outcome.message.contains("catalog"),
            "Message must tell the user to pick another car in the app"
        )

        let after = StorageService.shared.loadLastUserInput()
        XCTAssertEqual(after?.sourceVehicleId, Defaults.starterSourceVehicleId)
        XCTAssertTrue(after?.targetVehicleId.isEmpty == true)
        XCTAssertNotEqual(after?.targetVehicleId, Defaults.starterTargetVehicleId)
        XCTAssertNotEqual(after?.dailyKm, 15_000, "Must not save intent overrides when simulation is refused")
        XCTAssertEqual(WidgetSnapshotStore.load()?.updatedAt, widgetBefore)
        XCTAssertEqual(ScenarioHistoryStore.all().count, historyBefore)
    }

    @MainActor
    func testSimulateEVIntent_ValidPair_SummaryIncludesBothVehicleNames() {
        let sourceId = Defaults.starterSourceVehicleId
        let targetId = Defaults.starterTargetVehicleId
        guard let source = VehicleCatalogService.shared.vehicle(by: sourceId),
              let target = VehicleCatalogService.shared.vehicle(by: targetId) else {
            XCTFail("starter vehicles missing")
            return
        }
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourceVehicleId: sourceId,
            targetVehicleId: targetId,
            scenario: .realistic
        )
        StorageService.shared.saveUserInput(input)

        let outcome = SimulateEVIntentRunner.run(yearlyKm: 12_000, hasHomeCharging: true)
        XCTAssertTrue(outcome.didSimulate)
        XCTAssertTrue(outcome.message.contains(source.displayName), outcome.message)
        XCTAssertTrue(outcome.message.contains(target.displayName), outcome.message)
    }
}

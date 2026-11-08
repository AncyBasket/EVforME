import XCTest
@testable import EVforME_

/// Regression on real calc/UI gate paths: no silent 50 km, no artificial 10% floor,
/// no verdict until required PHEV fields are present and valid.
final class PHEVLogicHonestGatesTests: XCTestCase {
    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    private var sourceId: String {
        VehicleCatalogService.shared.vehicles.first(where: { $0.powertrain == .ice })?.id
            ?? "fiat-panda-2024"
    }

    private func completePHEVFixture(
        id: String = "fixture-phev-complete",
        rangeKm: Int? = 60,
        batteryKWh: Double? = 14,
        fuelLPerKm: Double? = 0.06,
        energyKWhPerKm: Double? = 0.18,
        energyIsWeighted: Bool? = false
    ) -> VehicleCatalogItem {
        VehicleCatalogItem(
            id: id,
            brand: "Fixture",
            model: "PHEV",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.4,
            widthM: 1.8,
            heightM: 1.5,
            fuelConsumptionLPerKm: fuelLPerKm,
            energyConsumptionKWhPerKm: energyKWhPerKm,
            maintenancePerYear: 280,
            taxesPerYear: 120,
            imageURL: nil,
            batteryKWh: batteryKWh,
            wltpRangeKm: rangeKm,
            fuelKind: .petrol,
            energyIsWeighted: energyIsWeighted
        )
    }

    private func baseInput(targetId: String) -> UserInput {
        UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.85,
            ownershipYears: 5,
            electricityPricePerKWh: 0.30,
            sourceVehicleId: sourceId,
            targetVehicleId: targetId,
            scenario: .realistic
        )
    }

    func testCompletePHEV_ShareUsesCatalogRange_NoSilentFifty() throws {
        // Public charging + mid km so raw stays below the 0.6 cap and differs from a 50 km stand-in.
        let phev = completePHEVFixture(rangeKm: 70)
        let share = try XCTUnwrap(phev.phevElectricKmShare(hasHomeCharging: false, yearlyKm: 18_000))
        let expectedRaw = min(0.6, 70.0 * 0.8 * 52.0 / 18_000.0)
        let silentFifty = min(0.6, max(0.1, 50.0 * 0.8 * 52.0 / 18_000.0))
        XCTAssertEqual(share, expectedRaw, accuracy: 0.0001)
        XCTAssertNotEqual(share, silentFifty, accuracy: 0.0001)
        XCTAssertNil(completePHEVFixture(rangeKm: nil).phevElectricKmShare(hasHomeCharging: false, yearlyKm: 18_000))
    }

    func testMissingEnergyOnly_NoShareUnlockFromBatteryOrWeighted() {
        let weightedOnly = completePHEVFixture(
            energyKWhPerKm: 0.20,
            energyIsWeighted: true
        )
        XCTAssertNil(weightedOnly.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertNil(weightedOnly.estimatedPHEVElectricRangeKm)
        // Catalog range still present → share ok, but real simulate path still needs CD energy.
        XCTAssertNotNil(weightedOnly.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000))
    }

    func testMissingEnergyOnly_BlocksVerdictOnRealIncompleteSeed() throws {
        // XC60 2024: CS present, CD missing, range present.
        let id = "volvo-xc60-phev-recharge-2024"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        XCTAssertNotNil(vehicle.usableChargeSustainingFuelLPerKm)
        XCTAssertNil(vehicle.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertNotNil(vehicle.catalogPHEVElectricRangeKm)

        var input = baseInput(targetId: id)
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(
            InputValidator.validate(input).contains(where: {
                $0 == L10n.validationIncompleteCatalogEnterEnergy
                    || $0 == L10n.validationMissingEnergyConsumption
            })
        )

        input.targetEnergyOverrideKWhPer100Km = 18
        // Preserve CS from catalog — do not require re-entering fuel.
        XCTAssertNil(input.targetFuelConsumptionOverrideLPer100Km)
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testMissingFuelOnly_BlocksUntilValidCSEntered() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        XCTAssertNil(vehicle.usableChargeSustainingFuelLPerKm)
        XCTAssertNil(vehicle.catalogPHEVElectricRangeKm)

        var input = baseInput(targetId: id)
        input.targetEnergyOverrideKWhPer100Km = 18
        input.targetElectricRangeOverrideKm = 55
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(
            InputValidator.validate(input).contains(where: {
                $0 == L10n.validationIncompleteCatalogEnterFuel
                    || $0 == L10n.validationMissingFuelConsumption
            })
        )

        input.targetFuelConsumptionOverrideLPer100Km = 6.5
        let result = try XCTUnwrap(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertFalse(result.keyReasons.isEmpty)
        // Valid fields kept.
        XCTAssertEqual(input.targetEnergyOverrideKWhPer100Km, 18)
        XCTAssertEqual(input.targetElectricRangeOverrideKm, 55)
    }

    func testMissingRangeOnly_BlocksVerdict_EstimateDoesNotUnlock() {
        let phev = completePHEVFixture(rangeKm: nil, batteryKWh: 18, energyKWhPerKm: 0.18)
        XCTAssertNil(phev.catalogPHEVElectricRangeKm)
        XCTAssertEqual(phev.estimatedPHEVElectricRangeKm ?? -1, 100, accuracy: 0.001)
        XCTAssertNil(phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000))
        XCTAssertNil(WeeklyChargeEstimator.declaredRangeKm(for: phev))
        XCTAssertEqual(WeeklyChargeEstimator.estimatedPHEVRangeKm(for: phev), 100)
    }

    func testMissingRangeOnSeed_RequiresRangeOverride_KeepsOtherOverrides() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        var input = baseInput(targetId: id)
        input.targetFuelConsumptionOverrideLPer100Km = 6.5
        input.targetEnergyOverrideKWhPer100Km = 18
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(InputValidator.validate(input).contains(L10n.validationIncompleteCatalogEnterRange))

        input.targetElectricRangeOverrideKm = 0
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(InputValidator.validate(input).contains(L10n.validationElectricRangeInvalid))

        input.targetElectricRangeOverrideKm = -10
        XCTAssertTrue(InputValidator.validate(input).contains(L10n.validationElectricRangeInvalid))

        input.targetElectricRangeOverrideKm = 55
        XCTAssertEqual(input.targetFuelConsumptionOverrideLPer100Km, 6.5)
        XCTAssertEqual(input.targetEnergyOverrideKWhPer100Km, 18)
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testMultipleMissingFields_AskAll_UnlockOnlyWhenAllValid() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        var input = baseInput(targetId: id)
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        let errors = InputValidator.validate(input)
        XCTAssertTrue(
            errors.contains(L10n.validationIncompleteCatalogEnterFuel)
                || errors.contains(L10n.validationMissingFuelConsumption),
            "fuel: \(errors)"
        )
        XCTAssertTrue(
            errors.contains(L10n.validationIncompleteCatalogEnterEnergy)
                || errors.contains(L10n.validationMissingEnergyConsumption),
            "energy: \(errors)"
        )
        XCTAssertTrue(errors.contains(L10n.validationIncompleteCatalogEnterRange), "range: \(errors)")

        input.targetFuelConsumptionOverrideLPer100Km = 6.5
        input.targetEnergyOverrideKWhPer100Km = 18
        input.targetElectricRangeOverrideKm = 50
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testInvalidUserInputs_ZeroNegativeRejected() throws {
        let phev = completePHEVFixture(rangeKm: nil)
        XCTAssertNil(EVSimulator.validElectricRangeKm(0))
        XCTAssertNil(EVSimulator.validElectricRangeKm(-5))
        XCTAssertNil(EVSimulator.validElectricRangeKm(.nan))
        XCTAssertEqual(EVSimulator.validElectricRangeKm(40), 40)

        XCTAssertNil(phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000, electricRangeKm: 0))
        XCTAssertNil(phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000, electricRangeKm: -1))
        XCTAssertNotNil(phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000, electricRangeKm: 40))
    }

    func testNoHomeChargingVsRegular_ShareDependsOnHabitsNotFloor() throws {
        let phev = completePHEVFixture(rangeKm: 40)
        let home = try XCTUnwrap(phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 20_000))
        let publicOnly = try XCTUnwrap(phev.phevElectricKmShare(hasHomeCharging: false, yearlyKm: 20_000))
        XCTAssertGreaterThan(home, publicOnly)
        // With short range + high km + no home, raw can be below the old 0.1 floor.
        let low = try XCTUnwrap(phev.phevElectricKmShare(hasHomeCharging: false, yearlyKm: 40_000))
        let raw = 40.0 * 0.8 * 52.0 / 40_000.0
        XCTAssertEqual(low, raw, accuracy: 0.0001)
        XCTAssertLessThan(low, 0.1)
    }

    func testVerdictBlockedThenUnlocked_PreservesPriorOverrides() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        var input = baseInput(targetId: id)
        input.targetFuelConsumptionOverrideLPer100Km = 6.2
        input.targetEnergyOverrideKWhPer100Km = 17.5
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))

        input.targetElectricRangeOverrideKm = 48
        let unlocked = try XCTUnwrap(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertEqual(input.targetFuelConsumptionOverrideLPer100Km, 6.2)
        XCTAssertEqual(input.targetEnergyOverrideKWhPer100Km, 17.5)
        XCTAssertEqual(input.targetElectricRangeOverrideKm, 48)
        XCTAssertGreaterThanOrEqual(unlocked.yearlySavingsRange.upperBound, unlocked.yearlySavingsRange.lowerBound)
    }

    func testCompleteSeedPHEV_StillSimulatesWithoutOverrides() throws {
        let id = "ford-kuga-phev-2023"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        XCTAssertEqual(vehicle.catalogDataIncomplete, false)
        XCTAssertNotNil(vehicle.usableChargeSustainingFuelLPerKm)
        XCTAssertNotNil(vehicle.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertNotNil(vehicle.catalogPHEVElectricRangeKm)
        let input = baseInput(targetId: id)
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testInvalidPositiveEnergy_RemainsNeeded_XC60() throws {
        let id = "volvo-xc60-phev-recharge-2024"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        XCTAssertNotNil(vehicle.usableChargeSustainingFuelLPerKm)
        XCTAssertNil(vehicle.usableChargeDepletingEnergyKWhPerKm)

        var input = baseInput(targetId: id)
        input.targetEnergyOverrideKWhPer100Km = 1 // positive but below 8…40 band
        XCTAssertTrue(
            VehicleCalcDataGate.needsEnergy(vehicle: vehicle, overrideKWhPer100: 1),
            "Invalid override must keep the energy field required"
        )
        XCTAssertFalse(VehicleCalcDataGate.hasSufficientCalcData(vehicle: vehicle, input: input, asSource: false))
        XCTAssertNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(InputValidator.validate(input).contains(L10n.validationStickerEnergyRange))

        // Fuel from catalog stays valid — do not re-ask.
        XCTAssertFalse(VehicleCalcDataGate.needsFuel(vehicle: vehicle, overrideLPer100: nil))
        XCTAssertNil(input.targetFuelConsumptionOverrideLPer100Km)

        input.targetEnergyOverrideKWhPer100Km = 18
        XCTAssertFalse(VehicleCalcDataGate.needsEnergy(vehicle: vehicle, overrideKWhPer100: 18))
        XCTAssertNotNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertEqual(input.targetEnergyOverrideKWhPer100Km, 18)
    }

    func testInvalidPositiveFuel_RemainsNeeded_WithOtherFieldsValid() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        var input = baseInput(targetId: id)
        input.targetEnergyOverrideKWhPer100Km = 18
        input.targetElectricRangeOverrideKm = 55
        input.targetFuelConsumptionOverrideLPer100Km = 2.5 // in sticker band but < 3 L/100 for PHEV
        XCTAssertTrue(VehicleCalcDataGate.needsFuel(vehicle: vehicle, overrideLPer100: 2.5))
        XCTAssertFalse(VehicleCalcDataGate.needsEnergy(vehicle: vehicle, overrideKWhPer100: 18))
        XCTAssertFalse(VehicleCalcDataGate.needsRange(vehicle: vehicle, overrideKm: 55))
        XCTAssertNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        XCTAssertNil(EVSimulator.simulate(input: input, scenario: .realistic))
        XCTAssertTrue(InputValidator.validate(input).contains(L10n.validationPHEVFuelTooLowForCalc))

        input.targetFuelConsumptionOverrideLPer100Km = 6.5
        XCTAssertEqual(input.targetEnergyOverrideKWhPer100Km, 18)
        XCTAssertEqual(input.targetElectricRangeOverrideKm, 55)
        XCTAssertNotNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testOperatingPreviewUnavailableUntilCS_CD_RangeValid() throws {
        let id = "cupra-formentor-phev-e-hybrid-2024"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        var input = baseInput(targetId: id)
        XCTAssertNil(OperatingCostCalculator.operatingCostPerYear(vehicle: vehicle, input: input, asSource: false))

        input.targetFuelConsumptionOverrideLPer100Km = 6.5
        XCTAssertNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        input.targetEnergyOverrideKWhPer100Km = 18
        XCTAssertNil(OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false))
        input.targetElectricRangeOverrideKm = 50
        let cost = try XCTUnwrap(
            OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false)
        )
        XCTAssertGreaterThan(cost, 0)
        XCTAssertNotNil(EVSimulator.simulate(input: input, scenario: .realistic))
    }

    func testCompleteCarsPreviewUnchanged() throws {
        let id = "ford-kuga-phev-2023"
        let vehicle = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: id))
        let input = baseInput(targetId: id)
        let cost = try XCTUnwrap(
            OperatingCostCalculator.operatingCostPerKm(vehicle: vehicle, input: input, asSource: false)
        )
        XCTAssertGreaterThan(cost, 0)
        let ice = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: sourceId))
        XCTAssertNotNil(OperatingCostCalculator.operatingCostPerKm(vehicle: ice, input: input, asSource: true))
    }
}

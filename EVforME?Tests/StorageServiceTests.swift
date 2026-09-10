//
//  StorageServiceTests.swift
//  EVforME?Tests
//
//  Unit tests per StorageService
//

import XCTest
@testable import EVforME_

final class StorageServiceTests: XCTestCase {

    override func setUp() {
        super.setUp()
        // Clean up any existing data
        let defaults = UserDefaults.standard
        defaults.removeObject(forKey: "evforme.lastUserInput")
        defaults.removeObject(forKey: "evforme.hasSeenOnboarding")
        defaults.removeObject(forKey: "evforme.autocosts.lastFuelPrice")
        defaults.removeObject(forKey: "evforme.autocosts.lastElectricityPrice")
        defaults.removeObject(forKey: "evforme.autocosts.userCustomizedFuelPrice")
        defaults.removeObject(forKey: "evforme.autocosts.userCustomizedElectricityPrice")
    }

    override func tearDown() {
        // Clean up after tests
        let defaults = UserDefaults.standard
        defaults.removeObject(forKey: "evforme.lastUserInput")
        defaults.removeObject(forKey: "evforme.hasSeenOnboarding")
        defaults.removeObject(forKey: "evforme.autocosts.lastFuelPrice")
        defaults.removeObject(forKey: "evforme.autocosts.lastElectricityPrice")
        defaults.removeObject(forKey: "evforme.autocosts.userCustomizedFuelPrice")
        defaults.removeObject(forKey: "evforme.autocosts.userCustomizedElectricityPrice")
        super.tearDown()
    }

    // MARK: - User Input Storage Tests

    func testSaveAndLoadUserInput() {
        // Given
        let service = StorageService.shared
        let originalInput = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.75,
            ownershipYears: 5,
            electricityPricePerKWh: 0.28,
            sourceVehicleId: "test-source",
            targetVehicleId: "test-target",
            scenario: .realistic
        )

        // When
        service.saveUserInput(originalInput)
        let loadedInput = service.loadLastUserInput()

        // Then
        XCTAssertNotNil(loadedInput)
        XCTAssertEqual(loadedInput?.dailyKm, originalInput.dailyKm)
        XCTAssertEqual(loadedInput?.hasHomeCharging, originalInput.hasHomeCharging)
        XCTAssertEqual(loadedInput?.areaType, originalInput.areaType)
        XCTAssertEqual(loadedInput?.fuelPrice, originalInput.fuelPrice)
        XCTAssertEqual(loadedInput?.ownershipYears, originalInput.ownershipYears)
        XCTAssertEqual(loadedInput?.electricityPricePerKWh, originalInput.electricityPricePerKWh)
        XCTAssertEqual(loadedInput?.sourceVehicleId, originalInput.sourceVehicleId)
        XCTAssertEqual(loadedInput?.targetVehicleId, originalInput.targetVehicleId)
        XCTAssertEqual(loadedInput?.scenario, originalInput.scenario)
    }

    func testLoadUserInput_WhenNoData_ReturnsNil() {
        // Given
        let service = StorageService.shared

        // When
        let loadedInput = service.loadLastUserInput()

        // Then
        XCTAssertNil(loadedInput)
    }

    func testSaveUserInput_OverwritesExistingData() {
        // Given
        let service = StorageService.shared
        let firstInput = UserInput(
            dailyKm: 10_000,
            hasHomeCharging: false,
            areaType: .mixed,
            fuelPrice: 1.5,
            ownershipYears: 3,
            scenario: .pessimistic
        )

        let secondInput = UserInput(
            dailyKm: 20_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.8,
            ownershipYears: 7,
            scenario: .optimistic
        )

        // When
        service.saveUserInput(firstInput)
        service.saveUserInput(secondInput)
        let loadedInput = service.loadLastUserInput()

        // Then
        XCTAssertEqual(loadedInput?.dailyKm, secondInput.dailyKm)
        XCTAssertEqual(loadedInput?.ownershipYears, secondInput.ownershipYears)
        XCTAssertEqual(loadedInput?.scenario, secondInput.scenario)
    }

    // MARK: - Onboarding Tests

    func testHasSeenOnboarding_DefaultValue() {
        // Given
        let service = StorageService.shared

        // When
        let hasSeenOnboarding = service.hasSeenOnboarding

        // Then
        XCTAssertFalse(hasSeenOnboarding)
    }

    func testMarkOnboardingSeen_SetsFlag() {
        // Given
        let service = StorageService.shared

        // When
        service.markOnboardingSeen()

        // Then
        XCTAssertTrue(service.hasSeenOnboarding)
    }

    // MARK: - Official Costs Application Tests

    func testApplyOfficialCostsIfNeeded_WhenUserHasNotCustomized() {
        // Given
        let service = StorageService.shared
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.5, // Old price
            ownershipYears: 5,
            electricityPricePerKWh: 0.20, // Old price
            scenario: .realistic
        )

        let newCosts = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.8,
            electricityPricePerKWh: 0.30,
            updatedAt: nil
        )

        // When
        let changed = service.applyOfficialCostsIfNeeded(newCosts, to: &input)

        // Then
        XCTAssertTrue(changed)
        XCTAssertEqual(input.fuelPrice, newCosts.fuelPricePerLiter)
        XCTAssertEqual(input.electricityPricePerKWh, newCosts.electricityPricePerKWh)
    }

    func testApplyOfficialCostsIfNeeded_WhenUserHasCustomized_DoesNotOverride() {
        // Given
        let service = StorageService.shared
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 2.0, // User custom price
            ownershipYears: 5,
            electricityPricePerKWh: 0.40, // User custom price
            scenario: .realistic
        )

        // Mark as user customized (manually set the flag for testing)
        let defaults = UserDefaults.standard
        defaults.set(true, forKey: "evforme.autocosts.userCustomizedFuelPrice")
        defaults.set(true, forKey: "evforme.autocosts.userCustomizedElectricityPrice")

        let newCosts = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.8,
            electricityPricePerKWh: 0.30,
            updatedAt: nil
        )

        // When
        let changed = service.applyOfficialCostsIfNeeded(newCosts, to: &input)

        // Then
        XCTAssertFalse(changed)
        XCTAssertEqual(input.fuelPrice, 2.0) // Should remain user's custom value
        XCTAssertEqual(input.electricityPricePerKWh, 0.40)
    }

    func testApplyOfficialCostsIfNeeded_WhenPricesAreSame_DoesNotChange() {
        // Given
        let service = StorageService.shared
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: 0.25,
            scenario: .realistic
        )

        let sameCosts = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.7,
            electricityPricePerKWh: 0.25,
            updatedAt: nil
        )

        // When
        let changed = service.applyOfficialCostsIfNeeded(sameCosts, to: &input)

        // Then
        XCTAssertFalse(changed)
    }

    // MARK: - Customization Flags Tests

    func testMarkFuelPriceCustomized_SetsFlag() {
        // Given
        let service = StorageService.shared

        // When
        service.markFuelPriceCustomized()

        // Then
        let defaults = UserDefaults.standard
        XCTAssertTrue(defaults.bool(forKey: "evforme.autocosts.userCustomizedFuelPrice"))
    }

    func testImportWidgetFuelCustomizationFlag_ImportsFlag() {
        // Given
        let service = StorageService.shared
        let suite = UserDefaults(suiteName: Defaults.appGroupID)
        suite?.set(true, forKey: "evforme.autocosts.userCustomizedFuelPrice")

        // When
        service.importWidgetFuelCustomizationFlag()

        // Then
        let defaults = UserDefaults.standard
        XCTAssertTrue(defaults.bool(forKey: "evforme.autocosts.userCustomizedFuelPrice"))
    }
}
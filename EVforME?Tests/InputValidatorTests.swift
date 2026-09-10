//
//  InputValidatorTests.swift
//  EVforME?Tests
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import XCTest
@testable import EVforME_

final class InputValidatorTests: XCTestCase {

    func testValidateDailyKm_ValidRange_ReturnsValid() {
        // Given — `dailyKm` nel modello è km/anno (min 1000).
        let km = 12_000
        
        // When
        let result = InputValidator.validateDailyKm(km)
        
        // Then
        if case .valid = result {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected valid result")
        }
    }
    
    func testValidateDailyKm_BelowMinimum_ReturnsInvalid() {
        // Given
        let km = 3
        
        // When
        let result = InputValidator.validateDailyKm(km)
        
        // Then
        if case .invalid(let message) = result {
            XCTAssertFalse(message.isEmpty)
        } else {
            XCTFail("Expected invalid result")
        }
    }
    
    func testValidateDailyKm_AboveMaximum_ReturnsInvalid() {
        // Given
        let km = 130_000
        
        // When
        let result = InputValidator.validateDailyKm(km)
        
        // Then
        if case .invalid(let message) = result {
            XCTAssertFalse(message.isEmpty)
        } else {
            XCTFail("Expected invalid result")
        }
    }
    
    func testValidateFuelPrice_ValidPrice_ReturnsValid() {
        // Given
        let price = 1.7
        
        // When
        let result = InputValidator.validateFuelPrice(price)
        
        // Then
        if case .valid = result {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected valid result")
        }
    }
    
    func testValidateElectricityPrice_Valid_ReturnsValid() {
        let result = InputValidator.validateElectricityPricePerKWh(0.35)
        if case .valid = result {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected valid")
        }
    }

    func testValidateElectricityPrice_TooHigh_ReturnsInvalid() {
        let result = InputValidator.validateElectricityPricePerKWh(2.5)
        if case .invalid = result {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected invalid")
        }
    }

    func testValidateFuelPrice_ZeroPrice_ReturnsInvalid() {
        // Given
        let price = 0.0
        
        // When
        let result = InputValidator.validateFuelPrice(price)
        
        // Then
        if case .invalid = result {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected invalid result")
        }
    }
    
    func testValidate_CompleteValidInput_ReturnsNoErrors() {
        // Given
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: 0.25,
            sourceVehicleId: "alfa-romeo-147-2005",
            targetVehicleId: "audi-q4-e-tron-2017",
            scenario: .realistic
        )
        
        // When
        let errors = InputValidator.validate(input)
        
        // Then
        XCTAssertTrue(errors.isEmpty)
    }
    
    func testValidate_InvalidInput_ReturnsErrors() {
        // Given
        let input = UserInput(
            dailyKm: 3,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 0,
            ownershipYears: 0,
            scenario: .realistic
        )
        
        // When
        let errors = InputValidator.validate(input)
        
        // Then
        XCTAssertFalse(errors.isEmpty)
    }
    
    // MARK: - Convenience Method Tests
    
    func testDailyKmValidation() {
        XCTAssertTrue(InputValidator.isDailyKmValid(12_000))
        XCTAssertFalse(InputValidator.isDailyKmValid(-5))
        XCTAssertFalse(InputValidator.isDailyKmValid(0))
        XCTAssertFalse(InputValidator.isDailyKmValid(500))
    }

    func testYearsValidation() {
        XCTAssertTrue(InputValidator.isYearsValid(5))
        XCTAssertFalse(InputValidator.isYearsValid(0))
        XCTAssertFalse(InputValidator.isYearsValid(50))
    }
}

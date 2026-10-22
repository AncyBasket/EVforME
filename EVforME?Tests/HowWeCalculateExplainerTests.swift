//
//  HowWeCalculateExplainerTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class HowWeCalculateExplainerTests: XCTestCase {

    func testFuelFromCO2Constants_MatchPythonScript() {
        // scripts/fill_catalog_fuels_from_eea.py → ≈ 22.63 / 26.25
        XCTAssertEqual(FuelFromCO2Constants.cPetrol, 0.1206, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.cDiesel, 0.1165, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.dPetrolKgPerL, 0.745, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.dDieselKgPerL, 0.834, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.co2Factor, 0.273, accuracy: 1e-12)
        // Script approx 22.63 / 26.25; exact values from the same coefficients.
        let expectedPetrol = FuelFromCO2Constants.dPetrolKgPerL
            / (FuelFromCO2Constants.cPetrol * FuelFromCO2Constants.co2Factor)
        let expectedDiesel = FuelFromCO2Constants.dDieselKgPerL
            / (FuelFromCO2Constants.cDiesel * FuelFromCO2Constants.co2Factor)
        XCTAssertEqual(FuelFromCO2Constants.petrolCO2PerL100, expectedPetrol, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.dieselCO2PerL100, expectedDiesel, accuracy: 1e-12)
        XCTAssertEqual(FuelFromCO2Constants.petrolCO2PerL100, 22.63, accuracy: 0.01)
        XCTAssertEqual(FuelFromCO2Constants.dieselCO2PerL100, 26.22, accuracy: 0.01)

        let petrolL100 = FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .petrol)
        XCTAssertEqual(petrolL100 ?? -1, 120 / FuelFromCO2Constants.petrolCO2PerL100, accuracy: 1e-9)
        let dieselL100 = FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .diesel)
        XCTAssertEqual(dieselL100 ?? -1, 120 / FuelFromCO2Constants.dieselCO2PerL100, accuracy: 1e-9)
    }

    func testBolloTariffs_MatchCalculationGetters() throws {
        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .molise)), 2.76, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(ItalianRegion.molise.evBolloEURPerKw), 2.76, accuracy: 1e-9)

        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .lazio)), 2.84, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(ItalianRegion.lazio.evBolloEURPerKw), 2.84, accuracy: 1e-9)

        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .lombardia)), 0, accuracy: 1e-9)
        XCTAssertTrue(ItalianRegion.lombardia.evPermanentlyExempt)

        XCTAssertEqual(
            try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .unspecified)),
            OwnershipCostEstimates.nationalEVBolloEURPerKw,
            accuracy: 1e-9
        )
        XCTAssertTrue(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .unspecified))
        XCTAssertFalse(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .molise))
        XCTAssertFalse(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .lazio))
    }

    func testSuperbolloConstants_MatchItalianRegion() {
        XCTAssertEqual(HowWeCalculateExplainer.superbolloThresholdKw, 185, accuracy: 1e-9)
        XCTAssertEqual(HowWeCalculateExplainer.superbolloEURPerKwAboveThreshold, 20, accuracy: 1e-9)
        let sb = ItalianRegion.nationalSuperbolloEUR(powerKw: 200, vehicleYear: 2024, referenceYear: 2026)
        XCTAssertEqual(sb, 20 * (200 - 185), accuracy: 1e-9)
        XCTAssertEqual(
            ItalianRegion.nationalSuperbolloEUR(powerKw: 185, vehicleYear: 2024, referenceYear: 2026),
            0,
            accuracy: 1e-9
        )
    }

    func testConfidenceBands() {
        XCTAssertEqual(ConfidenceBand.from(score: nil), .unknown)
        XCTAssertEqual(ConfidenceBand.from(score: 0.9), .high)
        XCTAssertEqual(ConfidenceBand.from(score: 0.8), .high)
        XCTAssertEqual(ConfidenceBand.from(score: 0.5), .medium)
        XCTAssertEqual(ConfidenceBand.from(score: 0.49), .low)
        XCTAssertEqual(HowWeCalculateExplainer.confidenceBand(for: 0.8), .high)
    }

    func testSourceURLExtraction() {
        let url = HowWeCalculateExplainer.sourceURL(
            from: "EEA CO2→FC — https://www.eea.europa.eu/data-and-maps"
        )
        XCTAssertEqual(url?.host, "www.eea.europa.eu")
        XCTAssertNil(HowWeCalculateExplainer.sourceURL(from: "scheda costruttore"))
    }

    func testFuelLikelyFromCO2() {
        XCTAssertTrue(HowWeCalculateExplainer.fuelLikelyFromCO2(sourceName: "EEA CO2→FC Reg. 2017/1151"))
        XCTAssertTrue(HowWeCalculateExplainer.fuelLikelyFromCO2(sourceName: "eea wltp fc fill"))
        XCTAssertFalse(HowWeCalculateExplainer.fuelLikelyFromCO2(sourceName: "Manufacturer WLTP sheet"))
    }

    func testMakeModel_BolloUsesSameConstants() throws {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            italianRegion: .molise
        )
        let model = HowWeCalculateExplainer.makeModel(userInput: input)
        XCTAssertEqual(try XCTUnwrap(model.bollo.evEURPerKw), 2.76, accuracy: 1e-9)
        XCTAssertEqual(model.bollo.petrolCO2PerL100, FuelFromCO2Constants.petrolCO2PerL100, accuracy: 1e-12)
        XCTAssertEqual(model.bollo.dieselCO2PerL100, FuelFromCO2Constants.dieselCO2PerL100, accuracy: 1e-12)
        XCTAssertEqual(model.bollo.superbolloThresholdKw, 185, accuracy: 1e-9)
        XCTAssertEqual(model.bollo.nationalEVBolloEURPerKw, OwnershipCostEstimates.nationalEVBolloEURPerKw, accuracy: 1e-9)
        XCTAssertEqual(model.eurLexURL, FuelFromCO2Constants.eurLexRegulationURL)
    }
}

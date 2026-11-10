//
//  PHEVWave2OfficialSourceTests.swift
//  EVforME?Tests
//
//  Regression for PHEV official-source rules (wave2 batch1).
//

import XCTest
@testable import EVforME_

final class PHEVWave2OfficialSourceTests: XCTestCase {

    func testPureElectricEnergyCiteRequiresPureLabel() {
        let weightedOnly = "Stromverbrauch ECAC gewichtet, kombiniert 16,0 kWh/100"
        let pure = "Stromverbrauch bei rein elektrischem Betrieb kombiniert 20,9–18,4 (solo elettrico / charge-depleting)"
        XCTAssertFalse(Self.looksLikePureElectricLabel(weightedOnly))
        XCTAssertTrue(Self.looksLikePureElectricLabel(pure))
    }

    func testCompleteFlagInconsistentWithMissingCalcFieldsFails() {
        let incomplete = VehicleCatalogItem(
            id: "test-phev-incomplete-flag",
            brand: "Test",
            model: "PHEV",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.5,
            widthM: 1.8,
            heightM: 1.6,
            fuelConsumptionLPerKm: 0.06,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 100,
            taxesPerYear: 50,
            imageURL: nil,
            batteryKWh: 12,
            wltpRangeKm: 50,
            energyIsWeighted: true,
            catalogDataIncomplete: false,
            missingCalcFields: ["energyConsumptionKWhPerKm"]
        )
        XCTAssertFalse(
            incomplete.resolvedMissingCalcFields.isEmpty,
            "Missing CD must surface in resolvedMissingCalcFields"
        )
        XCTAssertTrue(
            incomplete.hasIncompleteCatalogData == false
                && !incomplete.resolvedMissingCalcFields.isEmpty,
            "Probe: catalogDataIncomplete=false with missing fields must be detectable"
        )
    }

    func testFieldSourceDateRequiredForPastModelYearOfficialFill() throws {
        let kuga = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "ford-kuga-phev-2022"),
            "Kuga 2022 must exist after wave2 batch1"
        )
        XCTAssertEqual(kuga.year, 2022)
        XCTAssertFalse(kuga.hasIncompleteCatalogData)
        XCTAssertNotNil(kuga.energyConsumptionKWhPerKm)
        XCTAssertEqual(kuga.energyIsWeighted, false)
        let cite = try XCTUnwrap(kuga.fieldSource(for: "energyConsumptionKWhPerKm"))
        XCTAssertTrue(
            Self.looksLikePureElectricLabel(cite),
            "CD cite must carry a pure-electric label"
        )
        let date = try XCTUnwrap(kuga.fieldSourceDate(for: "energyConsumptionKWhPerKm"))
        XCTAssertFalse(date.isEmpty, "Every filled official field must have sourceDate")
        let src = kuga.sourceName ?? ""
        XCTAssertTrue(
            src.contains("stessa omologazione EEA") || src.contains("wave2-batch1"),
            "Homolog reuse must be cited in sourceName"
        )
    }

    func testBundledManifestIsSeed78() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"))
        let obj = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        )
        let version = (obj["seedVersion"] as? NSNumber)?.intValue
            ?? (obj["seedVersion"] as? Int)
        XCTAssertEqual(version, 78)
        XCTAssertEqual(VehicleCatalogService.bundledSeedVersion, 78)
    }

    private static func looksLikePureElectricLabel(_ cite: String) -> Bool {
        let patterns = [
            "solo elettrico",
            "charge-depleting",
            "charge depleting",
            "rein elektrischem",
            "pure electric",
            "consumo elettrico puro",
            "bei vollständig geladener"
        ]
        let lower = cite.lowercased()
        return patterns.contains { lower.contains($0) }
    }
}

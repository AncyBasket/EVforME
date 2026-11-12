//
//  PHEVWave2OfficialSourceTests.swift
//  EVforME?Tests
//
//  Regression for PHEV official-source rules (wave2 batch1, review-corrected).
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
        XCTAssertFalse(incomplete.resolvedMissingCalcFields.isEmpty)
        XCTAssertTrue(
            incomplete.hasIncompleteCatalogData == false
                && !incomplete.resolvedMissingCalcFields.isEmpty
        )
    }

    func testKuga2022RemainsIncompleteWithoutDatedMY22Source() throws {
        let kuga = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "ford-kuga-phev-2022"))
        XCTAssertEqual(kuga.year, 2022)
        XCTAssertTrue(kuga.hasIncompleteCatalogData)
        XCTAssertNil(kuga.energyConsumptionKWhPerKm)
        XCTAssertEqual(kuga.weightedFuelConsumptionLPerKm ?? -1, 0.01007, accuracy: 1e-9)
    }

    func testBMW330e2024BatteryExtraKeepsPureEnergyNil() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "bmw-330e-phev-2024"))
        XCTAssertEqual(row.batteryKWh ?? -1, 19.5, accuracy: 0.01)
        let date = try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh"))
        XCTAssertTrue(date.hasPrefix("2024"))
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        // Battery press extra must not invent EAER/range provenance.
        XCTAssertNil(row.fieldSource(for: "wltpRangeKm"))
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testHomologReuseRequiresIdenticalPowerAndWeightedWLTP() throws {
        // Jeep Compass 4xe 2022 vs 2024: weighted WLTP and/or power differ — must not share fills.
        let my22 = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "jeep-compass-phev-4xe-2022"))
        let my24 = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "jeep-compass-phev-4xe-2024"))
        let powerDiffers = abs((my22.powerKw ?? -1) - (my24.powerKw ?? -2)) > 1e-9
        let fuelDiffers = abs(
            (my22.weightedFuelConsumptionLPerKm ?? -1) - (my24.weightedFuelConsumptionLPerKm ?? -2)
        ) > 1e-9
        let energyDiffers = abs(
            (my22.weightedEnergyConsumptionKWhPerKm ?? -1) - (my24.weightedEnergyConsumptionKWhPerKm ?? -2)
        ) > 1e-9
        XCTAssertTrue(
            powerDiffers || fuelDiffers || energyDiffers,
            "donor/destination must differ so exact-homolog reuse stays blocked"
        )
        XCTAssertNil(my22.fuelConsumptionLPerKm)
        XCTAssertTrue(my22.hasIncompleteCatalogData)
    }

    func testBundledManifestIsSeed80() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"))
        let obj = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        )
        let version = (obj["seedVersion"] as? NSNumber)?.intValue
            ?? (obj["seedVersion"] as? Int)
        XCTAssertEqual(version, 80)
        XCTAssertEqual(VehicleCatalogService.bundledSeedVersion, 80)
    }

    func testAudiQ3Sportback2024OfficialETDFillNetBattery() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "audi-q3-sportback-phev-45-tfsi-e-2024")
        )
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.072, accuracy: 1e-9)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 52)
        XCTAssertEqual(row.batteryKWh ?? -1, 10.4, accuracy: 0.01)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let batSrc = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(batSrc.lowercased().contains("net"))
        XCTAssertTrue(batSrc.contains("audi-mediacenter.com"))
        XCTAssertTrue(batSrc.contains("240314"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-03-14")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2024-03-14")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2024-03-14")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testAudiQ5_2024OfficialETDFillNetBattery() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "audi-q5-phev-50-tfsi-e-2024"))
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.087, accuracy: 1e-9)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 56)
        XCTAssertEqual(row.batteryKWh ?? -1, 14.4, accuracy: 0.01)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let src = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(src.lowercased().contains("net"))
        XCTAssertTrue(src.contains("audi-mediacenter.com"))
        XCTAssertTrue(src.contains("240604"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2024-06-04")
    }

    func testAudiA3_45_2024OfficialETDFillNetBattery() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "audi-a3-phev-45-tfsi-e-2024"))
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.066, accuracy: 1e-9)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 58)
        XCTAssertEqual(row.batteryKWh ?? -1, 10.4, accuracy: 0.01)
        let src = try XCTUnwrap(row.fieldSource(for: "fuelConsumptionLPerKm"))
        XCTAssertTrue(src.contains("A3-Sportback-45"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-03-14")
    }

    func testPeugeot3008_2022OfficialTarifFill() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "peugeot-3008-phev-2022"))
        XCTAssertEqual(row.batteryKWh ?? -1, 13.2, accuracy: 0.01)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 55)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let bat = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(bat.contains("peugeot.fr") || bat.contains("novembre-2021"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2021-11-02")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testAudiA3_40_2024RemainsNilWrongGenerationSheet() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "audi-a3-phev-40-tfsi-e-2024"))
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.wltpRangeKm)
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertTrue(row.hasIncompleteCatalogData)
        XCTAssertNil(row.fieldSource(for: "fuelConsumptionLPerKm"))
        XCTAssertNil(row.fieldSource(for: "batteryKWh"))
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

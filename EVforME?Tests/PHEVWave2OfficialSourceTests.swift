//
//  PHEVWave2OfficialSourceTests.swift
//  EVforME?Tests
//
//  Regression for PHEV official-source rules (wave2 batch1 + batch2).
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

    func testBundledManifestIsSeed88() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"))
        let obj = try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        )
        let version = (obj["seedVersion"] as? NSNumber)?.intValue
            ?? (obj["seedVersion"] as? Int)
        XCTAssertEqual(version, 88)
        XCTAssertEqual(VehicleCatalogService.bundledSeedVersion, 88)
    }

    // MARK: - Wave2 batch3 research fills

    func testEvoque2023UsableBatteryOfficial() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "land-rover-range-rover-evoque-phev-2023")
        )
        XCTAssertEqual(row.batteryKWh ?? -1, 12.1, accuracy: 0.01)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.wltpRangeKm)
        let batSrc = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(batSrc.lowercased().contains("usable"))
        XCTAssertTrue(batSrc.contains("landrover.com"))
        XCTAssertTrue(batSrc.lowercased().contains("metadati") || batSrc.lowercased().contains("creationdate"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2023-06-14")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testMazdaCX60_2023EAERCombinedOfficial() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "mazda-cx-60-phev-2023")
        )
        XCTAssertEqual(row.wltpRangeKm ?? -1, 63)
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        let src = try XCTUnwrap(row.fieldSource(for: "wltpRangeKm"))
        XCTAssertTrue(src.contains("mazda.eu") || src.contains("mazda"))
        XCTAssertTrue(src.contains("63"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2023-07-03")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testMitsubishiEclipse2023PureCDOfficial() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "mitsubishi-eclipse-cross-phev-2023")
        )
        XCTAssertEqual(row.usableChargeDepletingEnergyKWhPerKm ?? -1, 0.175, accuracy: 1e-9)
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        let src = try XCTUnwrap(row.fieldSource(for: "energyConsumptionKWhPerKm"))
        XCTAssertTrue(src.lowercased().contains("rein elektrisch") || src.lowercased().contains("charge-depleting"))
        XCTAssertTrue(src.contains("mitsubishi-motors.at"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "energyConsumptionKWhPerKm")), "2023-04-27")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testPeugeot308_2022RemainsNilWithoutMY22OEMSheet() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "peugeot-308-phev-2022")
        )
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.wltpRangeKm)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertTrue(row.hasIncompleteCatalogData)
        let sn = row.sourceName ?? ""
        XCTAssertTrue(sn.contains("wave2-batch3 left_nil") || sn.lowercased().contains("consulted"))
        XCTAssertTrue(sn.contains("media.stellantis.com") || sn.contains("peugeot308"))
    }

    func testGolfGTE_2024CSDischargedAndNetBatteryOfficial() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-gte-phev-2024")
        )
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.054, accuracy: 1e-9)
        XCTAssertEqual(row.batteryKWh ?? -1, 19.7, accuracy: 0.01)
        XCTAssertNil(row.wltpRangeKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let cs = try XCTUnwrap(row.fieldSource(for: "fuelConsumptionLPerKm"))
        XCTAssertTrue(cs.lowercased().contains("discharged") || cs.lowercased().contains("battery discharged"))
        XCTAssertTrue(cs.contains("18398"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-05-16")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2024-05-16")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testDS7_2024AggregateCSMaxAcrossVariants() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "ds-7-phev-e-tense-2024"))
        XCTAssertEqual(row.batteryKWh ?? -1, 13.0, accuracy: 0.01)
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.082, accuracy: 1e-9)
        XCTAssertNil(row.wltpRangeKm)
        let cs = try XCTUnwrap(row.fieldSource(for: "fuelConsumptionLPerKm"))
        XCTAssertTrue(cs.contains("8,2") || cs.contains("0.082"))
        XCTAssertTrue(cs.lowercased().contains("360") || cs.lowercased().contains("max"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-03-25")
    }

    func testBYDSealU_2024UsesPDFCreationDate() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "byd-seal-u-phev-dm-i-2024"))
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.074, accuracy: 1e-9)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 70)
        XCTAssertNil(row.batteryKWh)
        let src = try XCTUnwrap(row.fieldSource(for: "fuelConsumptionLPerKm"))
        XCTAssertTrue(src.lowercased().contains("metadati") || src.lowercased().contains("creationdate"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-05-23")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2024-05-23")
    }

    // MARK: - Wave2 batch2 research fills

    func testAudiQ5Sportback2024OfficialETDFill() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "audi-q5-sportback-phev-50-tfsi-e-2024")
        )
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.088, accuracy: 1e-9)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 57)
        XCTAssertEqual(row.batteryKWh ?? -1, 14.4, accuracy: 0.01)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let batSrc = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(batSrc.lowercased().contains("net"))
        XCTAssertTrue(batSrc.contains("audi-mediacenter.com"))
        XCTAssertTrue(batSrc.contains("240604") || batSrc.contains("06/04/24"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-06-04")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2024-06-04")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2024-06-04")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testBMWX1_30e_2023OfficialNettaAndEAER() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "bmw-x1-phev-xdrive30e-2023")
        )
        XCTAssertEqual(row.batteryKWh ?? -1, 14.2, accuracy: 0.01)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 71)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        let batSrc = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(batSrc.lowercased().contains("netto") || batSrc.lowercased().contains("net"))
        XCTAssertTrue(batSrc.contains("cdn.mportal.de") || batSrc.contains("U11-11-2023"))
        XCTAssertFalse(batSrc.contains("T0322775"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2023-09-27")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2023-09-27")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testBMWX3_30e_2024OfficialNetAndEAER() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "bmw-x3-phev-xdrive30e-2024")
        )
        XCTAssertEqual(row.batteryKWh ?? -1, 19.7, accuracy: 0.01)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 81)
        XCTAssertEqual(row.fuelConsumptionLPerKm ?? -1, 0.079, accuracy: 1e-9)
        let batSrc = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(batSrc.lowercased().contains("net"))
        XCTAssertTrue(batSrc.contains("T0443191EL"))
        XCTAssertTrue(batSrc.contains("19.06.2024"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2024-06-19")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2024-06-19")
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "fuelConsumptionLPerKm")), "2024-06-19")
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testAudiQ5Sportback2023RemainsNilWithoutMY23OEMSheet() throws {
        let row = try XCTUnwrap(
            VehicleCatalogService.shared.vehicle(by: "audi-q5-sportback-phev-50-tfsi-e-2023")
        )
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.wltpRangeKm)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertNil(row.fieldSource(for: "batteryKWh"))
        XCTAssertNil(row.fieldSource(for: "wltpRangeKm"))
        XCTAssertTrue(row.hasIncompleteCatalogData)
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

    func testPeugeot3008_2022RemainsNilWithoutVerifiedMY22NetSource() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "peugeot-3008-phev-2022"))
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.wltpRangeKm)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertNil(row.usableChargeDepletingEnergyKWhPerKm)
        XCTAssertNil(row.fieldSource(for: "batteryKWh"))
        XCTAssertNil(row.fieldSource(for: "wltpRangeKm"))
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testBMWX1_2022BatteryIsNettaNotGross() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "bmw-x1-phev-xdrive25e-2022"))
        XCTAssertEqual(row.batteryKWh ?? -1, 8.82, accuracy: 0.01)
        let src = try XCTUnwrap(row.fieldSource(for: "batteryKWh"))
        XCTAssertTrue(src.lowercased().contains("netta") || src.lowercased().contains("net"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "batteryKWh")), "2022-01-26")
        let sn = row.sourceName ?? ""
        XCTAssertTrue(
            sn.contains("Capacità lorda/netta 10/8.82, memorizzato netto 8.82"),
            "sourceName must state lorda/netta 10/8.82 and memorizzato netto 8.82"
        )
        XCTAssertFalse(sn.lowercased().contains("batteria 10 kwh"))
        XCTAssertEqual(row.wltpRangeKm ?? -1, 49)
        XCTAssertNil(row.fuelConsumptionLPerKm)
        XCTAssertTrue(row.hasIncompleteCatalogData)
    }

    func testPeugeot3008_2023AggregateBatteryNilPrudentRange48() throws {
        let row = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "peugeot-3008-phev-2023"))
        // Aggregate IT PHEV (trim PHEV) — not clearly HYBRID 225; Usable 10.4 is 225/300 only.
        XCTAssertNil(row.batteryKWh)
        XCTAssertNil(row.fieldSource(for: "batteryKWh"))
        // 29.8 mi × 1.609344 = 47.96… → floor 47 (prudent min; never round up to 48)
        XCTAssertEqual(row.wltpRangeKm ?? -1, 47)
        let rangeSrc = try XCTUnwrap(row.fieldSource(for: "wltpRangeKm"))
        XCTAssertTrue(rangeSrc.contains("HYBRID 180") || rangeSrc.lowercased().contains("29.8"))
        XCTAssertTrue(rangeSrc.lowercased().contains("floor") || rangeSrc.contains("47"))
        XCTAssertEqual(try XCTUnwrap(row.fieldSourceDate(for: "wltpRangeKm")), "2023-04-01")
        let sn = row.sourceName ?? ""
        XCTAssertFalse(sn.contains("bat 14.2"))
        XCTAssertFalse(sn.lowercased().contains("battery 14.2"))
        XCTAssertNil(row.fuelConsumptionLPerKm)
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

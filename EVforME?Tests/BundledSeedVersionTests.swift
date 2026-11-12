//
//  BundledSeedVersionTests.swift
//  EVforME?Tests
//
//  Regression: bundled seed revision must track Data/catalog_cdn.json, not a stale literal.
//

import XCTest
@testable import EVforME_

final class BundledSeedVersionTests: XCTestCase {

    override func tearDown() {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        super.tearDown()
    }

    /// Single source of truth: runtime version == seedVersion in bundled catalog_cdn.json.
    func testBundledSeedVersionMatchesCatalogCDNManifest() throws {
        let manifestVersion = try Self.readBundledManifestSeedVersion()
        XCTAssertEqual(manifestVersion, 79, "Manifest after PHEV wave2 batch1 research is seed 79")
        XCTAssertEqual(
            VehicleCatalogService.bundledSeedVersion,
            manifestVersion,
            "bundledSeedVersion must be derived from catalog_cdn.json, not a stale hardcoded value"
        )
    }

    /// Guards against reintroducing `static let bundledSeedVersion = <int>` that drifts from the manifest.
    func testVehicleCatalogServiceSourceDoesNotHardcodeBundledSeedVersion() throws {
        let sourceURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // EVforME?Tests
            .deletingLastPathComponent() // repo root
            .appendingPathComponent("EVforME?/Core/Logic/VehicleCatalogService.swift")
        let source = try String(contentsOf: sourceURL, encoding: .utf8)
        let regex = try NSRegularExpression(
            pattern: #"static\s+let\s+bundledSeedVersion\s*=\s*(\d+)"#,
            options: []
        )
        let range = NSRange(source.startIndex..<source.endIndex, in: source)
        let matches = regex.matches(in: source, options: [], range: range)
        XCTAssertTrue(
            matches.isEmpty,
            "VehicleCatalogService must not hardcode bundledSeedVersion; read it from catalog_cdn.json"
        )
    }

    /// Install with cacheSeedVersion=65 + stale catalog file must re-seed to manifest 79
    /// without wiping persisted user input / preferences.
    func testUpgradeFromCachedSeed65ReseedsCatalogButPreservesUserInput() throws {
        let storage = StorageService.shared
        let saved = UserInput(
            dailyKm: 18_500,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            electricityPricePerKWh: 0.42,
            sourceVehicleId: "fiat-panda-2018",
            targetVehicleId: "tesla-model-3-trazione-posteriore-2026",
            scenario: .realistic
        )
        storage.saveUserInput(saved)

        let staleMarker = VehicleCatalogItem(
            id: "stale-seed-65-marker",
            brand: "Stale",
            model: "Cache65",
            year: 2010,
            powertrain: .ice,
            lengthM: 4.0,
            widthM: 1.8,
            heightM: 1.5,
            fuelConsumptionLPerKm: 0.06,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 100,
            taxesPerYear: 50,
            imageURL: nil
        )
        VehicleCatalogService.shared.plantCatalogCacheForTesting(version: 65, catalog: [staleMarker])
        XCTAssertEqual(VehicleCatalogService.shared.cachedSeedVersionForTesting(), 65)

        VehicleCatalogService.shared.reloadRespectingCatalogCacheForTesting()

        XCTAssertEqual(
            VehicleCatalogService.shared.cachedSeedVersionForTesting(),
            VehicleCatalogService.bundledSeedVersion,
            "Cache seed version must advance to the bundled manifest revision"
        )
        XCTAssertNil(
            VehicleCatalogService.shared.vehicle(by: "stale-seed-65-marker"),
            "Stale cached catalog from seed 65 must be replaced"
        )
        XCTAssertNotNil(
            VehicleCatalogService.shared.vehicle(by: "tesla-model-3-trazione-posteriore-2026"),
            "Bundled seed catalog must be loaded after upgrade"
        )
        XCTAssertGreaterThanOrEqual(
            VehicleCatalogService.shared.vehicles.count,
            1000,
            "Re-seed must load the full quality seed, not the tiny defaultCatalog"
        )

        let restored = try XCTUnwrap(storage.loadLastUserInput())
        XCTAssertEqual(restored.sourceVehicleId, "fiat-panda-2018")
        XCTAssertEqual(restored.targetVehicleId, "tesla-model-3-trazione-posteriore-2026")
        XCTAssertEqual(restored.dailyKm, 18_500)
        XCTAssertEqual(restored.electricityPricePerKWh, 0.42, accuracy: 0.001)
    }

    private static func readBundledManifestSeedVersion() throws -> Int {
        let url = try XCTUnwrap(
            Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"),
            "catalog_cdn.json must be in the app bundle"
        )
        let data = try Data(contentsOf: url)
        let obj = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any],
            "catalog_cdn.json must be a JSON object"
        )
        if let number = obj["seedVersion"] as? NSNumber {
            return number.intValue
        }
        return try XCTUnwrap(obj["seedVersion"] as? Int, "seedVersion missing in catalog_cdn.json")
    }
}

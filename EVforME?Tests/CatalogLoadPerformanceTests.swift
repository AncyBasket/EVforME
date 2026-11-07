//
//  CatalogLoadPerformanceTests.swift
//  EVforME?Tests
//
//  Documents catalog decode cost (os_signpost CatalogLoad in the app).
//  Before: Task { @MainActor } decoded on the main thread (~same ms, blocked UI).
//  After: DispatchQueue.global decode, apply on main.
//

import XCTest
@testable import EVforME_

final class CatalogLoadPerformanceTests: XCTestCase {

    func testBundledSeedDecode_CompletesUnderBudget() throws {
        let url = try XCTUnwrap(
            Bundle.main.url(forResource: "vehicles.seed.quality", withExtension: "json"),
            "vehicles.seed.quality.json must be in the app host bundle"
        )
        let data = try Data(contentsOf: url)
        XCTAssertGreaterThan(data.count, 1_000_000)

        var decodedCount = 0
        let start = CFAbsoluteTimeGetCurrent()
        let decoded = try JSONDecoder().decode([VehicleCatalogItem].self, from: data)
        let ms = (CFAbsoluteTimeGetCurrent() - start) * 1000
        decodedCount = decoded.count
        XCTAssertGreaterThan(decodedCount, 5000)
        // Simulator budget: decode alone should stay well under a UI-kill window.
        XCTAssertLessThan(ms, 5_000, "Bundled seed JSON decode took \(ms)ms for \(decodedCount) rows")
        print("CatalogLoadPerformance: decode \(String(format: "%.0f", ms))ms rows=\(decodedCount) bytes=\(data.count)")
    }

    func testCatalogService_ReloadDoesNotLeaveEmptyCatalog() {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        XCTAssertGreaterThan(VehicleCatalogService.shared.vehicles.count, 5000)
    }

    func testBundledSeedVersionAndRowCountMatchManifest() throws {
        let manifestURL = try XCTUnwrap(
            Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"),
            "catalog_cdn.json must be included with the bundled seed"
        )
        let manifestData = try Data(contentsOf: manifestURL)
        let manifest = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: manifestData) as? [String: Any]
        )
        let manifestVersion = try XCTUnwrap(manifest["seedVersion"] as? Int)
        let manifestRows = try XCTUnwrap(manifest["rows"] as? Int)
        let manifestBytes = try XCTUnwrap(manifest["bytes"] as? Int)
        let seedURL = try XCTUnwrap(
            Bundle.main.url(forResource: "vehicles.seed.quality", withExtension: "json")
        )
        let seedData = try Data(contentsOf: seedURL)
        let seed = try JSONDecoder().decode(
            [VehicleCatalogItem].self,
            from: seedData
        )

        XCTAssertEqual(VehicleCatalogService.bundledSeedVersion, manifestVersion)
        XCTAssertEqual(seed.count, manifestRows)
        XCTAssertEqual(seedData.count, manifestBytes)
    }
}

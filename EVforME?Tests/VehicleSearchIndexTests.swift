//
//  VehicleSearchIndexTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class VehicleSearchIndexTests: XCTestCase {

    private var index: VehicleSearchIndex!

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        let vehicles = VehicleCatalogService.shared.vehicles
        XCTAssertFalse(vehicles.isEmpty, "Bundled catalog must load")
        index = VehicleSearchIndex(vehicles: vehicles)
    }

    func testEmptyQuery_BrowseIsBrandThenModels_NotFlatDump() {
        let brands = index.allBrands(popularFirst: ["Fiat", "Volkswagen", "Tesla"])
        XCTAssertGreaterThan(brands.count, 20)
        XCTAssertEqual(brands.first, "Fiat")

        let fiatModels = index.models(forBrand: "Fiat")
        XCTAssertFalse(fiatModels.isEmpty)
        XCTAssertTrue(fiatModels.allSatisfy { $0.brand.caseInsensitiveCompare("Fiat") == .orderedSame })

        // Empty text search without brand is allowed but browse APIs are preferred.
        let flat = index.search(query: "", limit: 40)
        XCTAssertLessThanOrEqual(flat.count, 40)
    }

    func testTextSearch_GroupedByBrand() {
        let grouped = index.searchGrouped(query: "golf", limit: 40)
        XCTAssertFalse(grouped.isEmpty)
        for section in grouped {
            XCTAssertFalse(section.models.isEmpty)
            XCTAssertTrue(section.models.allSatisfy { $0.brand == section.brand })
        }
        // VW Golf should dominate; no random cross-brand dump without hierarchy.
        XCTAssertTrue(grouped.contains(where: { $0.brand.localizedCaseInsensitiveContains("Volkswagen") }))
    }

    func testItalianAliases_Serie3_Model3_ID3() {
        let serie3 = index.search(query: "serie 3", limit: 20)
        XCTAssertTrue(serie3.contains(where: { $0.brand == "BMW" && $0.model.localizedCaseInsensitiveContains("3") }))

        let model3 = index.search(query: "model 3", limit: 20)
        XCTAssertTrue(model3.contains(where: { $0.brand == "Tesla" && $0.model.localizedCaseInsensitiveContains("Model 3") }))

        let id3 = index.search(query: "id.3", limit: 20)
        XCTAssertTrue(id3.contains(where: { $0.brand == "Volkswagen" && $0.model.localizedCaseInsensitiveContains("ID") }))
    }

    func testCanonicalSpelling_CollapsesModel3Variants() {
        let a = VehicleSearchIndex.canonicalGroupKey(brand: "Tesla", model: "Model 3")
        let b = VehicleSearchIndex.canonicalGroupKey(brand: "Tesla", model: "model3")
        XCTAssertEqual(a, b)
    }
}

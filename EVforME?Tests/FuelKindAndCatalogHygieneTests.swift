//
//  FuelKindAndCatalogHygieneTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class FuelKindAndCatalogHygieneTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    func testAteca2016_IsDieselForITHeuristic() {
        let ateca = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016")
        XCTAssertNotNil(ateca)
        XCTAssertEqual(ateca?.fuelKind, .diesel)
        XCTAssertEqual(ateca?.resolvedFuelKind, .diesel)
        XCTAssertEqual(ateca?.catalogFuelLabel, L10n.powertrainDieselLabel)
        // Uso reale ~7–8 L/100 (non WLTP ottimistico ~6.3).
        let l100 = (ateca?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(l100, 7.0)
        XCTAssertLessThanOrEqual(l100, 9.0)
    }

    func testPanda_IsPetrol() {
        let panda = VehicleCatalogService.shared.vehicle(by: "fiat-panda-2018")
            ?? VehicleCatalogService.shared.sourceVehicles().first { $0.model == "Panda" }
        XCTAssertNotNil(panda)
        XCTAssertEqual(panda?.resolvedFuelKind, .petrol)
    }

    func testOfficialCosts_DieselPricePreferred() {
        let costs = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.80,
            dieselPricePerLiter: 1.65,
            electricityPricePerKWh: 0.30,
            updatedAt: nil
        )
        XCTAssertEqual(costs.pricePerLiter(for: .diesel), 1.65, accuracy: 0.0001)
        XCTAssertEqual(costs.pricePerLiter(for: .petrol), 1.80, accuracy: 0.0001)
    }

    func testCatalog_NoImpossibleAtecaPre2016() {
        let years = VehicleCatalogService.shared.vehicles
            .filter { $0.brand == "SEAT" && $0.model == "Ateca" }
            .map(\.year)
        XCTAssertFalse(years.contains { $0 < 2016 })
        XCTAssertTrue(years.contains(2016))
    }

    func testCatalog_NoJunkRadiatorNames() {
        let junk = VehicleCatalogService.shared.vehicles.filter(\.isJunkCatalogEntry)
        XCTAssertTrue(junk.isEmpty, "Junk entries should be filtered on load")
    }

    func testOperatingValueBasis_ListPriceOnOldCar_IsHaircut() {
        let basis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: 40_000,
            vehicleYear: 2016,
            electrified: false,
            referenceYear: 2026
        )
        XCTAssertLessThan(basis, 40_000)
    }

    func testOperatingValueBasis_AlreadyUsedEstimate_NotDoubleDepreciated() {
        // Stessa curva di Defaults.suggestedPurchasePrice per ICE 2016 → ~7_500.
        let suggestedUsed = 7_500.0
        let basis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: suggestedUsed,
            vehicleYear: 2016,
            electrified: false,
            referenceYear: 2026
        )
        XCTAssertEqual(basis, suggestedUsed, accuracy: 0.01)
    }
}

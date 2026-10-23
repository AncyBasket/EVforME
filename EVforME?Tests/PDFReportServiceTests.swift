//
//  PDFReportServiceTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class PDFReportServiceTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    func testPdfBreakEvenLine_OwnedMode_OmitsNotReachedWhenNil() {
        var input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 7,
            electricityPricePerKWh: 0.25,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023",
            comparisonIntent: .alreadyOwned
        )
        let result = EVSimulator.simulate(input: input)
        XCTAssertNotNil(result)
        XCTAssertNil(result?.breakEvenMonths, "Owned mode should not expose purchase break-even")
        let line = PDFReportService.pdfBreakEvenLine(result: result!, input: input)
        XCTAssertTrue(line.isEmpty, "Must not print break_even_not_reached in owned mode: \(line)")
        _ = input
    }

    func testPdfBreakEvenLine_PurchaseMode_ShowsNotReachedWhenNil() {
        var input = UserInput(
            dailyKm: 8_000,
            hasHomeCharging: false,
            areaType: .mixed,
            fuelPrice: 1.50,
            ownershipYears: 3,
            electricityPricePerKWh: 0.55,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023",
            sourcePurchasePrice: 5_000,
            targetPurchasePrice: 55_000,
            comparisonIntent: .consideringPurchase
        )
        guard let result = EVSimulator.simulate(input: input) else {
            XCTFail("simulate failed")
            return
        }
        if result.breakEvenMonths == nil {
            let line = PDFReportService.pdfBreakEvenLine(result: result, input: input)
            XCTAssertEqual(line, L10n.breakEvenNotReachedReason)
        } else {
            let line = PDFReportService.pdfBreakEvenLine(result: result, input: input)
            XCTAssertEqual(line, L10n.breakEvenMonthsBadge(result.breakEvenMonths!))
        }
        _ = input
    }
}

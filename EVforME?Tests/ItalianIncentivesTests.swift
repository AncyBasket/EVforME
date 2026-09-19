//
//  ItalianIncentivesTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class ItalianIncentivesTests: XCTestCase {
    @MainActor
    func testBundledScheduleMatchesHistoricalBrackets() async {
        let schedule = await ItalianIncentivesService.shared.refresh()
        XCTAssertEqual(schedule.country, "IT")
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 6_000, accuracy: 0.01)
        XCTAssertEqual(ItalianIncentives.typicalPurchaseBonusEUR, 6_000, accuracy: 0.01)
    }

    func testOverMaxListPriceReturnsZero() {
        let bonus = ItalianIncentiveSchedule.bundledFallback.estimatedPurchaseBonusEUR(
            evListPrice: 50_000,
            replacingVehiclePrice: 10_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 0, accuracy: 0.01)
    }
}

//
//  ItalianIncentivesTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class ItalianIncentivesTests: XCTestCase {
    @MainActor
    func testBundledScheduleIsIllustrativeOnly_NotAutoApplied() async {
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.cached.v1")
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.lastFetchAt")
        let schedule = await ItalianIncentivesService.shared.refresh()
        XCTAssertEqual(schedule.country, "IT")
        XCTAssertTrue(
            (schedule.sourceNote ?? "").localizedCaseInsensitiveContains("verifica")
                || (schedule.sourceNote ?? "").localizedCaseInsensitiveContains("verify")
                || (schedule.sourceNote ?? "").localizedCaseInsensitiveContains("ufficiale")
                || (schedule.sourceNote ?? "").localizedCaseInsensitiveContains("official"),
            "Bundle must tell users to verify on the official site"
        )
        // Exact illustrative figure from italian_incentives.json brackets (≤45k → 9000).
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 9_000, accuracy: 0.01)
        XCTAssertEqual(ItalianIncentives.typicalPurchaseBonusEUR, 9_000, accuracy: 0.01)
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            sourcePurchasePrice: 12_000,
            targetPurchasePrice: 32_000,
            comparisonIntent: .consideringPurchase
        )
        XCTAssertFalse(input.includeIncentives)
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0)
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

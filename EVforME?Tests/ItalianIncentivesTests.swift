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
        // Illustrative figure still computes, but UserInput defaults includeIncentives=false.
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
        XCTAssertGreaterThan(bonus, 0)
        var input = UserInput(
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

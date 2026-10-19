//
//  ItalianIncentivesTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class ItalianIncentivesTests: XCTestCase {
    @MainActor
    func testBundledScheduleIsClosed_NotAutoApplied() async {
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.cached.v1")
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.lastFetchAt")
        let schedule = await ItalianIncentivesService.shared.refresh()
        XCTAssertEqual(schedule.country, "IT")
        XCTAssertEqual(schedule.validUntil, "2026-06-30")
        XCTAssertEqual(schedule.maxListPriceEUR, 35_000, accuracy: 0.01)
        // Oggi > validUntil → incentivo 0 e copy senza "entro".
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 0, accuracy: 0.01)
        XCTAssertEqual(ItalianIncentives.typicalPurchaseBonusEUR, 0, accuracy: 0.01)
        let badge = ItalianIncentives.windowBadgeText
        XCTAssertFalse(badge.localizedCaseInsensitiveContains("entro"))
        XCTAssertFalse(badge.localizedCaseInsensitiveContains("buy by"))
        XCTAssertTrue(badge.localizedCaseInsensitiveContains("chiuso") || badge.localizedCaseInsensitiveContains("closed"))
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            sourcePurchasePrice: 12_000,
            targetPurchasePrice: 32_000,
            includeIncentives: true,
            comparisonIntent: .consideringPurchase
        )
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0)
    }

    func testOverMaxListPriceReturnsZero() {
        let schedule = ItalianIncentiveSchedule(
            country: "IT",
            currency: "EUR",
            updatedAt: nil,
            validFrom: "2025-01-01",
            validUntil: "2099-12-31",
            maxListPriceEUR: 35_000,
            maxBonusEUR: 11_000,
            scrappageExtraEUR: 0,
            scrappageMaxReplacingPriceEUR: 0,
            brackets: [ItalianIncentiveBracket(maxPriceEUR: 35_000, bonusEUR: 9_000)],
            sourceNote: nil
        )
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 50_000,
            replacingVehiclePrice: 10_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 0, accuracy: 0.01)
    }

    func testActiveWindowStillYieldsBracketBonus() {
        let schedule = ItalianIncentiveSchedule(
            country: "IT",
            currency: "EUR",
            updatedAt: nil,
            validFrom: "2025-01-01",
            validUntil: "2099-12-31",
            maxListPriceEUR: 35_000,
            maxBonusEUR: 11_000,
            scrappageExtraEUR: 0,
            scrappageMaxReplacingPriceEUR: 0,
            brackets: [ItalianIncentiveBracket(maxPriceEUR: 35_000, bonusEUR: 9_000)],
            sourceNote: nil
        )
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
        XCTAssertEqual(bonus, 9_000, accuracy: 0.01)
    }
}

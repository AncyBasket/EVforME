//
//  ItalianIncentiveScheduleTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class ItalianIncentiveScheduleTests: XCTestCase {
    @MainActor
    func testBundledRefreshExposesWindowFields() async {
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.cached.v1")
        UserDefaults.standard.removeObject(forKey: "evforme.italianIncentives.lastFetchAt")
        let schedule = await ItalianIncentivesService.shared.refresh()
        XCTAssertEqual(schedule.validUntil, "2026-12-31")
        XCTAssertNotNil(schedule.validUntilDate)
        if case .active(let until) = schedule.windowStatus(asOf: date("2026-06-15")) {
            XCTAssertEqual(until, schedule.validUntilDate)
        } else {
            XCTFail("Expected active window in mid-2026")
        }
    }

    func testValidUntilFutureIsActive() {
        let schedule = makeSchedule(validUntil: "2099-12-31")
        if case .active = schedule.windowStatus(asOf: date("2026-09-20")) {
            XCTAssertFalse(schedule.isSchedulePossiblyStale)
        } else {
            XCTFail("Expected active")
        }
    }

    func testValidUntilPastIsExpired() {
        let schedule = makeSchedule(validUntil: "2020-01-01")
        if case .expired = schedule.windowStatus(asOf: date("2026-09-20")) {
            XCTAssertTrue(schedule.isSchedulePossiblyStale)
        } else {
            XCTFail("Expected expired")
        }
    }

    func testMissingDatesUnknown() {
        let schedule = makeSchedule(validUntil: nil)
        XCTAssertEqual(schedule.windowStatus(asOf: date("2026-09-20")), .unknown)
    }

    func testRetrocompatibleDecodeWithoutWindowKeys() throws {
        let json = """
        {
          "country": "IT",
          "currency": "EUR",
          "maxListPriceEUR": 45000,
          "maxBonusEUR": 7000,
          "scrappageExtraEUR": 2000,
          "scrappageMaxReplacingPriceEUR": 18000,
          "brackets": [{ "maxPriceEUR": 30000, "bonusEUR": 5000 }]
        }
        """.data(using: .utf8)!
        let decoded = try JSONDecoder().decode(ItalianIncentiveSchedule.self, from: json)
        XCTAssertNil(decoded.validUntil)
        XCTAssertEqual(decoded.windowStatus(), .unknown)
        XCTAssertEqual(
            decoded.estimatedPurchaseBonusEUR(evListPrice: 28_000, replacingVehiclePrice: 0, hasHomeCharging: true),
            5_000,
            accuracy: 0.01
        )
    }

    func testBolloEVExemptInFirstYears() {
        let bollo = OwnershipCostEstimates.bolloPerYearEstimate(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2024,
            referenceYear: 2026
        )
        XCTAssertEqual(bollo, 0, accuracy: 0.01)
    }

    func testBolloICEUsesCatalog() {
        let bollo = OwnershipCostEstimates.bolloPerYearEstimate(
            catalogTaxesPerYear: 210,
            powertrain: .ice,
            vehicleYear: 2018,
            referenceYear: 2026
        )
        XCTAssertEqual(bollo, 210, accuracy: 0.01)
    }

    private func makeSchedule(validUntil: String?) -> ItalianIncentiveSchedule {
        ItalianIncentiveSchedule(
            country: "IT",
            currency: "EUR",
            updatedAt: nil,
            validFrom: nil,
            validUntil: validUntil,
            maxListPriceEUR: 45_000,
            maxBonusEUR: 7_000,
            scrappageExtraEUR: 2_000,
            scrappageMaxReplacingPriceEUR: 18_000,
            brackets: [ItalianIncentiveBracket(maxPriceEUR: 30_000, bonusEUR: 5_000)],
            sourceNote: nil
        )
    }

    private func date(_ isoDay: String) -> Date {
        ItalianIncentiveSchedule.parseFlexibleDate(isoDay)!
    }
}

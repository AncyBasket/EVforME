//
//  AppMarketTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class AppMarketTests: XCTestCase {

    func testFromIsoCountryCode_KnownAndAliases() {
        XCTAssertEqual(AppMarket.from(isoCountryCode: "IT"), .IT)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "it"), .IT)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "DE"), .DE)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "GB"), .GB)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "UK"), .GB)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "US"), .US)
    }

    func testFromIsoCountryCode_UnknownFallsBackToOther() {
        XCTAssertEqual(AppMarket.from(isoCountryCode: "ZZ"), .other)
        XCTAssertEqual(AppMarket.from(isoCountryCode: "XX"), .other)
        XCTAssertEqual(AppMarket.from(isoCountryCode: ""), AppMarket.fromDeviceLocale())
        XCTAssertEqual(AppMarket.from(isoCountryCode: nil), AppMarket.fromDeviceLocale())
    }

    func testFromDeviceLocale_MatchesRegionOrOther() {
        let market = AppMarket.fromDeviceLocale()
        if let region = Locale.current.region?.identifier.uppercased(),
           let exact = AppMarket(rawValue: region == "UK" ? "GB" : region) {
            XCTAssertEqual(market, exact)
        } else {
            // Unsupported region codes map to .other (or alias).
            let code = Locale.current.region?.identifier.uppercased()
            if code == "UK" {
                XCTAssertEqual(market, .GB)
            } else {
                XCTAssertEqual(market, AppMarket.from(isoCountryCode: code))
            }
        }
    }

    func testShowsItalyCostKit_OnlyForItaly() {
        var input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            market: .IT
        )
        XCTAssertTrue(input.showsItalyCostKit)

        input.market = .DE
        XCTAssertFalse(input.showsItalyCostKit)

        input.market = .other
        XCTAssertFalse(input.showsItalyCostKit)
    }

    func testIncentivesZeroOutsideItaly() {
        var input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.8,
            ownershipYears: 5,
            sourcePurchasePrice: 12_000,
            targetPurchasePrice: 35_000,
            includeIncentives: true,
            comparisonIntent: .consideringPurchase,
            market: .IT
        )
        // Outside IT must be zero regardless of includeIncentives / intent.
        // IT may be >0 depending on bundled schedule brackets.
        let italyBonus = input.estimatedPurchaseIncentiveEUR
        XCTAssertEqual(input.market, .IT)

        input.market = .DE
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0)
        // Restore IT and confirm gate is market-only (same prices).
        input.market = .IT
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, italyBonus)

        input.market = .US
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0)

        input.market = .other
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0)
    }

    func testMaintenanceRates_DifferByCluster() {
        let it = MarketMaintenanceRates.rates(for: .IT)
        let de = MarketMaintenanceRates.rates(for: .DE)
        let uk = MarketMaintenanceRates.rates(for: .GB)
        let us = MarketMaintenanceRates.rates(for: .US)
        let other = MarketMaintenanceRates.rates(for: .other)

        XCTAssertEqual(AppMarket.IT.costCluster, .southernEU)
        XCTAssertEqual(AppMarket.DE.costCluster, .centralEU)
        XCTAssertEqual(AppMarket.GB.costCluster, .uk)
        XCTAssertEqual(AppMarket.US.costCluster, .northAmerica)
        XCTAssertEqual(AppMarket.other.costCluster, .worldDefault)
        XCTAssertNotEqual(it.iceEURPerYearAt15k, de.iceEURPerYearAt15k)
        XCTAssertNotEqual(uk.evEURPerYearAt15k, us.evEURPerYearAt15k)
        XCTAssertGreaterThan(other.iceEURPerYearAt15k, 0)
    }
}

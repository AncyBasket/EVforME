//
//  HardcodedURLHygieneTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class HardcodedURLHygieneTests: XCTestCase {
    func testOfficialLinks_AreHTTPSAndWellFormed() {
        for url in OfficialLinks.allHTTPSLinks {
            XCTAssertEqual(url.scheme?.lowercased(), "https", "\(url) must be https")
            XCTAssertNotNil(url.host, "\(url) must have a host")
            XCTAssertFalse(url.host!.isEmpty)
            XCTAssertNil(url.user, "\(url) must not embed credentials")
            XCTAssertNil(url.password)
        }
    }

    func testItalianIncentivesLink_IsMASEBonusPortal() {
        XCTAssertEqual(
            OfficialLinks.italianVehicleIncentives.host,
            "www.bonusveicolielettrici.mase.gov.it"
        )
    }

    func testDefaultsEnergyURLs_AreHTTPS() {
        XCTAssertTrue(Defaults.mimitFuelPricesCSVURL.hasPrefix("https://"))
        XCTAssertTrue(Defaults.eurostatElectricityURL.hasPrefix("https://"))
        XCTAssertNotNil(URL(string: Defaults.mimitFuelPricesCSVURL))
        XCTAssertNotNil(URL(string: Defaults.eurostatElectricityURL))
    }
}

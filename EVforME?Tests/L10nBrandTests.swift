//
//  L10nBrandTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class L10nBrandTests: XCTestCase {

    func testAppTitleNeverLocalized() {
        XCTAssertEqual(L10n.appTitle, "EVforME?")

        for lang in ["it", "en"] {
            guard let path = Bundle.main.path(forResource: lang, ofType: "lproj"),
                  let bundle = Bundle(path: path) else {
                XCTFail("Missing \(lang).lproj in app bundle")
                continue
            }
            let title = NSLocalizedString("app_title", tableName: nil, bundle: bundle, value: "", comment: "")
            XCTAssertEqual(title, "EVforME?", "app_title in \(lang).lproj must stay EVforME?")
            let onboarding = NSLocalizedString("onboarding_title", tableName: nil, bundle: bundle, value: "", comment: "")
            XCTAssertEqual(onboarding, "EVforME?", "onboarding_title in \(lang).lproj must stay EVforME?")
        }
    }

    func testShellEditionYearYY_UsesGregorianNotJapanese() {
        var components = DateComponents()
        components.year = 2026
        components.month = 6
        components.day = 15
        let gregorian = Calendar(identifier: .gregorian)
        let date = gregorian.date(from: components)!

        XCTAssertEqual(L10n.shellEditionYearYY(from: date, calendar: gregorian), 26)

        // Calendario giapponese sull’identica istante: non deve finire nel badge.
        var japanese = Calendar(identifier: .japanese)
        japanese.locale = Locale(identifier: "ja_JP")
        let japaneseYear = japanese.component(.year, from: date)
        XCTAssertNotEqual(japaneseYear % 100, 26, "Japanese era year must differ from Gregorian YY")
        XCTAssertEqual(
            L10n.shellEditionYearYY(from: date),
            26,
            "Default shellEditionYearYY must force Gregorian even if Calendar.current is Japanese"
        )
    }
}

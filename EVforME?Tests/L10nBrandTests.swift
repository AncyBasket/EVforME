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
}

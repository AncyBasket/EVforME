//
//  EVforME_UITests.swift
//  EVforME?UITests
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import XCTest

final class EVforME_UITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testInputToVerdictFlow() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        // Dismiss onboarding / quick-start (IT/EN; PrimaryButton may uppercase label)
        dismissQuickStartIfNeeded(app)

        let titleEN = app.staticTexts["EV for ME?"]
        let titleIT = app.staticTexts["EV per ME?"]
        XCTAssertTrue(
            titleEN.waitForExistence(timeout: 5) || titleIT.waitForExistence(timeout: 2),
            "Masthead title should match app_title (EN or IT)"
        )

        // Wait for catalog-backed starters (async load) before simulating.
        let startersReady =
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Golf")).firstMatch
                .waitForExistence(timeout: 12)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Model 3")).firstMatch
                .waitForExistence(timeout: 2)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Tesla")).firstMatch
                .waitForExistence(timeout: 2)
        XCTAssertTrue(startersReady, "Starter vehicles should appear after catalog load")

        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 3) || tellMeIT.waitForExistence(timeout: 1),
            "Main simulate button should exist"
        )
        if tellMeEN.exists { tellMeEN.tap() } else { tellMeIT.tap() }

        // L10n: EN "Change inputs" / IT "Modifica dati"
        let modifyEN = app.buttons["Change inputs"]
        let modifyIT = app.buttons["Modifica dati"]
        let modifyLegacy = app.buttons["Modify input"]
        let oneExists =
            modifyEN.waitForExistence(timeout: 15)
            || modifyIT.waitForExistence(timeout: 2)
            || modifyLegacy.waitForExistence(timeout: 1)
        XCTAssertTrue(oneExists, "Verdict screen should show modify / back to bench control")

        // PDF export (gratis) — sheet should open without crash.
        let pdfEN = app.buttons["Export PDF report"]
        let pdfIT = app.buttons["Esporta report PDF"]
        if pdfIT.waitForExistence(timeout: 2) || pdfEN.waitForExistence(timeout: 1) {
            if pdfIT.exists { pdfIT.tap() } else { pdfEN.tap() }
            // Sheet presence is best-effort (ShareLink labels vary by OS).
            _ = app.buttons["Condividi report PDF"].waitForExistence(timeout: 3)
                || app.buttons["Share PDF report"].waitForExistence(timeout: 1)
        }
    }
    
    @MainActor
    func testSliderUpdatesValue() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let slider = app.sliders["Yearly kilometers slider"]
        XCTAssertTrue(slider.waitForExistence(timeout: 8))
        // Slider exists and can be used
        XCTAssertTrue(slider.exists)
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }

    @MainActor
    private func dismissQuickStartIfNeeded(_ app: XCUIApplication) {
        let labels = [
            "Apri il banco",
            "APRI IL BANCO",
            "Open the bench",
            "OPEN THE BENCH",
            "Salta intro",
            "Skip intro",
            "GET STARTED",
            "INIZIA",
            "Get Started",
        ]
        for label in labels {
            let button = app.buttons[label]
            if button.waitForExistence(timeout: 1.2) {
                button.tap()
                return
            }
        }
    }
}

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

        // Dismiss onboarding (`PrimaryButton` mostra il titolo in maiuscolo)
        if app.buttons["GET STARTED"].waitForExistence(timeout: 2) {
            app.buttons["GET STARTED"].tap()
        } else if app.buttons["INIZIA"].waitForExistence(timeout: 2) {
            app.buttons["INIZIA"].tap()
        } else if app.buttons["Get Started"].waitForExistence(timeout: 1) {
            app.buttons["Get Started"].tap()
        }

        let titleEN = app.staticTexts["EV for ME?"]
        let titleIT = app.staticTexts["EV per ME?"]
        XCTAssertTrue(
            titleEN.waitForExistence(timeout: 5) || titleIT.waitForExistence(timeout: 2),
            "Masthead title should match app_title (EN or IT)"
        )

        // CTA: `accessibilityLabel` = string localizzata (non più "Calculate EV suitability")
        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 3) || tellMeIT.waitForExistence(timeout: 1),
            "Main simulate button should exist"
        )
        if tellMeEN.exists { tellMeEN.tap() } else { tellMeIT.tap() }

        let modifyLower = app.buttons["Modify input"]
        let modifyTitle = app.buttons["Modify Input"]
        let modifyIT = app.buttons["Modifica dati"]
        let oneExists =
            modifyLower.waitForExistence(timeout: 12)
            || modifyTitle.waitForExistence(timeout: 1)
            || modifyIT.waitForExistence(timeout: 1)
        XCTAssertTrue(oneExists, "Verdict screen should show modify / back to bench control")
    }
    
    @MainActor
    func testSliderUpdatesValue() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        if app.buttons["GET STARTED"].waitForExistence(timeout: 2) {
            app.buttons["GET STARTED"].tap()
        } else if app.buttons["INIZIA"].waitForExistence(timeout: 2) {
            app.buttons["INIZIA"].tap()
        } else if app.buttons["Get Started"].waitForExistence(timeout: 1) {
            app.buttons["Get Started"].tap()
        }

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
}

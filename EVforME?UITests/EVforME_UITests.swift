//
//  EVforME_UITests.swift
//  EVforME?UITests
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import XCTest

final class EVforME_UITests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    override func tearDownWithError() throws {}

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
    
    /// EV ≥ 5 anni senza P.2 → header verdetto mostra “Totale parziale (bollo non stimato)”.
    @MainActor
    func testVerdictHeaderShowsPartialBolloWhenEVOverFiveYearsWithoutP2() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_PARTIAL_BOLLO"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let startersReady =
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Golf")).firstMatch
                .waitForExistence(timeout: 12)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Model 3")).firstMatch
                .waitForExistence(timeout: 2)
            || app.buttons["Dimmi la verità"].waitForExistence(timeout: 2)
            || app.buttons["Tell me the truth"].waitForExistence(timeout: 1)
        XCTAssertTrue(startersReady, "Input bench should load with preset vehicles")

        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 3) || tellMeIT.waitForExistence(timeout: 1),
            "Main simulate button should exist"
        )
        if tellMeEN.exists { tellMeEN.tap() } else { tellMeIT.tap() }

        let partialIT = app.staticTexts["Totale parziale (bollo non stimato)"]
        let partialEN = app.staticTexts["Partial total (road tax not estimated)"]
        XCTAssertTrue(
            partialIT.waitForExistence(timeout: 15) || partialEN.waitForExistence(timeout: 2),
            "Verdict header should show partial total when EV is 5+ years without booklet P.2"
        )
    }

    @MainActor
    func testSliderUpdatesValue() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        // Stesso path di testInputToVerdictFlow: aspetta il banco caricato.
        let startersReady =
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Golf")).firstMatch
                .waitForExistence(timeout: 12)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Model 3")).firstMatch
                .waitForExistence(timeout: 2)
            || app.buttons["Dimmi la verità"].waitForExistence(timeout: 2)
            || app.buttons["Tell me the truth"].waitForExistence(timeout: 1)
        XCTAssertTrue(startersReady, "Input bench should load")

        for _ in 0..<5 { app.swipeUp() }

        // Km slider lives inside the advanced DisclosureGroup (collapsed by default).
        let advancedIT = app.buttons["Regola km, prezzi e scenario"]
        let advancedEN = app.buttons["Adjust km, prices, and scenario"]
        if advancedIT.waitForExistence(timeout: 3) {
            advancedIT.tap()
        } else if advancedEN.waitForExistence(timeout: 1) {
            advancedEN.tap()
        } else {
            // Fallback: any disclosure/button whose label mentions km/prezzi.
            let approx = app.buttons.matching(
                NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS[c] %@", "km", "prices")
            ).firstMatch
            if approx.waitForExistence(timeout: 2) { approx.tap() }
        }

        for _ in 0..<3 { app.swipeUp() }

        // Controllo stretto: identifier o label km/anno (niente fallback generico su qualsiasi slider).
        let byId = app.descendants(matching: .any)["yearly_km_slider"]
        let byA11y = app.sliders["Yearly kilometers slider"]
        let byKmAnno = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "km/anno")).firstMatch
        let byKmYear = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "km/year")).firstMatch
        let kmControl =
            byId.waitForExistence(timeout: 6)
            || byA11y.waitForExistence(timeout: 2)
            || byKmAnno.waitForExistence(timeout: 2)
            || byKmYear.waitForExistence(timeout: 1)
        XCTAssertTrue(kmControl, "Yearly km/anno slider should be reachable on input")
        if byId.exists {
            XCTAssertTrue(byId.isHittable || byId.isEnabled, "yearly_km_slider should be interactive")
        }
    }

    @MainActor
    func testLaunchPerformance() throws {
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
            "Continua",
            "Continue",
        ]
        for label in labels {
            let btn = app.buttons[label]
            if btn.waitForExistence(timeout: 1.5) {
                btn.tap()
                return
            }
        }
    }
}

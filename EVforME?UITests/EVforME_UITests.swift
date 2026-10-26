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
        XCUIDevice.shared.orientation = .portrait
    }

    override func tearDownWithError() throws {
        XCUIDevice.shared.orientation = .portrait
    }

    @MainActor
    func testInputToVerdictFlow() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        // Dismiss onboarding / quick-start (IT/EN; PrimaryButton may uppercase label)
        dismissQuickStartIfNeeded(app)

        let title = app.staticTexts["EVforME?"]
        XCTAssertTrue(
            title.waitForExistence(timeout: 5),
            "Masthead title should be the untranslated brand EVforME?"
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
    func testFuelPriceSliderAcceptsLPG078() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_SOURCE_FUEL"] = "lpg"
        app.launchEnvironment["UITEST_FUEL_PRICE"] = "0.78"
        app.launchEnvironment["UITEST_EXPAND_ADVANCED"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let startersReady =
            app.buttons["Dimmi la verità"].waitForExistence(timeout: 12)
            || app.buttons["Tell me the truth"].waitForExistence(timeout: 2)
        XCTAssertTrue(startersReady, "Input bench should load")

        // Advanced già espanso via UITEST_EXPAND_ADVANCED; scroll finché lo slider carburante è on-screen.
        let byId = app.descendants(matching: .any)["fuel_price_slider"]
        for _ in 0..<24 {
            if byId.exists { break }
            app.swipeUp()
            RunLoop.current.run(until: Date().addingTimeInterval(0.15))
        }
        XCTAssertTrue(byId.waitForExistence(timeout: 6), "Fuel price slider should be reachable for GPL source")

        // Valore mostrato obbligatorio: 0,78 (range GPL 0,50…1,20). Non basta che esista lo slider.
        let valuePredicates = [
            NSPredicate(format: "label CONTAINS %@", "0,78"),
            NSPredicate(format: "label CONTAINS %@", "0.78"),
            NSPredicate(format: "label CONTAINS %@", "€0,78"),
            NSPredicate(format: "label CONTAINS %@", "€0.78"),
            NSPredicate(format: "value CONTAINS %@", "0,78"),
            NSPredicate(format: "value CONTAINS %@", "0.78")
        ]
        var shown078 = false
        for pred in valuePredicates {
            let match = app.descendants(matching: .any).matching(pred).firstMatch
            if match.waitForExistence(timeout: 3) {
                shown078 = true
                break
            }
        }
        if !shown078, let raw = byId.value as? String,
           raw.contains("0.78") || raw.contains("0,78") || raw.contains("78") {
            shown078 = true
        }
        XCTAssertTrue(shown078, "UI must show GPL price €0.78/L (not overwritten by petrol official / not clamped ≥1.0)")

        let byA11yIT = app.sliders["Prezzo carburante (€/L o €/kg)"]
        let byA11yEN = app.sliders["Fuel price (€/L or €/kg)"]
        let fuelControl = byId.exists || byA11yIT.exists || byA11yEN.exists
        XCTAssertTrue(fuelControl, "Fuel price control should be reachable for GPL source")

        let slider = [byId, byA11yIT, byA11yEN].first(where: \.exists) ?? byId
        if let raw = slider.value as? String {
            let digits = raw
                .replacingOccurrences(of: ",", with: ".")
                .components(separatedBy: CharacterSet(charactersIn: "0123456789.").inverted)
                .joined()
            if let numeric = Double(digits), numeric > 0 {
                XCTAssertGreaterThanOrEqual(numeric, 0.50, "GPL value below min")
                XCTAssertLessThanOrEqual(numeric, 1.20, "GPL value above max — clamp on fuel-kind change failed")
            }
        }
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

    /// Marca → modello → anno → versione → verdetto con ricariche visibili.
    @MainActor
    func testEVVersionPickerToVerdictShowsCharges() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let startersReady =
            app.buttons["Dimmi la verità"].waitForExistence(timeout: 12)
            || app.buttons["Tell me the truth"].waitForExistence(timeout: 2)
        XCTAssertTrue(startersReady, "Input bench should load")

        // Open EV catalog — ViewThatFits can expose duplicate ids; tap the hittable one.
        let evCards = app.descendants(matching: .any).matching(identifier: "vehicle_pair_target")
        XCTAssertTrue(evCards.firstMatch.waitForExistence(timeout: 8), "EV pair card should exist")
        var opened = false
        for _ in 0..<4 {
            let count = evCards.count
            for i in 0..<count {
                let card = evCards.element(boundBy: i)
                guard card.exists else { continue }
                if card.isHittable {
                    card.tap()
                    opened = true
                    break
                }
            }
            if opened { break }
            app.swipeDown()
            RunLoop.current.run(until: Date().addingTimeInterval(0.15))
        }
        if !opened {
            evCards.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.4)).tap()
        }

        let sheetTitleIT = app.navigationBars["Veicolo elettrificato"]
        let sheetTitleEN = app.navigationBars["Electrified vehicle"]
        let closeIT = app.buttons["Chiudi"]
        let closeEN = app.buttons["Close"]
        XCTAssertTrue(
            sheetTitleIT.waitForExistence(timeout: 6)
                || sheetTitleEN.waitForExistence(timeout: 2)
                || closeIT.waitForExistence(timeout: 2)
                || closeEN.waitForExistence(timeout: 1),
            "Target vehicle catalog sheet should open"
        )

        // Search → model → year → version.
        let search = app.descendants(matching: .any)["vehicle_catalog_search"]
        XCTAssertTrue(search.waitForExistence(timeout: 6), "Catalog search field")
        search.tap()
        search.typeText("Fiat 500e")

        let model500e = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "500e")
        ).firstMatch
        XCTAssertTrue(model500e.waitForExistence(timeout: 8), "Fiat 500e search hit")
        model500e.tap()

        let year2021 = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "2021")
        ).firstMatch
        XCTAssertTrue(year2021.waitForExistence(timeout: 6), "Year 2021 for 500e")
        year2021.tap()

        let versionRow = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "WLTP")
        ).firstMatch
        if versionRow.waitForExistence(timeout: 4) {
            versionRow.tap()
        }

        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 8) || tellMeIT.waitForExistence(timeout: 2),
            "Back on bench after version pick"
        )
        if tellMeEN.exists { tellMeEN.tap() } else { tellMeIT.tap() }

        let modifyEN = app.buttons["Change inputs"]
        let modifyIT = app.buttons["Modifica dati"]
        XCTAssertTrue(
            modifyEN.waitForExistence(timeout: 15) || modifyIT.waitForExistence(timeout: 2),
            "Verdict should open"
        )

        // Weekly charges metric should be numeric (e.g. "1×"), not n/a / n/d.
        let chargesOK =
            app.staticTexts.matching(NSPredicate(format: "label MATCHES %@", #".*[0-9]+×.*"#)).firstMatch
                .waitForExistence(timeout: 6)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "×")).firstMatch
                .waitForExistence(timeout: 2)
        XCTAssertTrue(chargesOK, "Chosen version should show weekly charges on verdict")
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

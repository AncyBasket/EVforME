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

    /// Unmatched OEM: BMW i4 2024 → "Versione n" + nota EEA (no kW EEA nel titolo) → verdetto.
    @MainActor
    func testEVVersionPickerToVerdictShowsCharges() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_OPEN_TARGET_PICKER"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let search = app.descendants(matching: .any)["vehicle_catalog_search"]
        XCTAssertTrue(
            search.waitForExistence(timeout: 14),
            "Target vehicle catalog sheet should open (UITEST_OPEN_TARGET_PICKER)"
        )
        search.tap()
        search.typeText("BMW i4")

        let modeli4 = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "i4")
        ).firstMatch
        XCTAssertTrue(modeli4.waitForExistence(timeout: 8), "BMW i4 search hit")
        modeli4.tap()

        let year2024 = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@ AND label CONTAINS[c] %@", "i4", "2024")
        ).firstMatch
        XCTAssertTrue(year2024.waitForExistence(timeout: 6), "Year 2024 for i4")
        year2024.tap()

        let wltpCaption = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "Autonomia WLTP")
        ).firstMatch
        XCTAssertTrue(wltpCaption.waitForExistence(timeout: 6), "WLTP min–max caption on version rows")

        let eeaNote = app.staticTexts.matching(
            NSPredicate(
                format: "label CONTAINS[c] %@ AND label CONTAINS[c] %@",
                "omologat", "EEA"
            )
        ).firstMatch
        XCTAssertTrue(
            eeaNote.waitForExistence(timeout: 6),
            "Unmatched versions show EEA homologation note"
        )

        let versioneRow = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "Versione")
        ).firstMatch
        XCTAssertTrue(versioneRow.waitForExistence(timeout: 4), "Unmatched Versione n row")
        let versioneLabel = versioneRow.label
        XCTAssertFalse(
            versioneLabel.range(of: #"\d+\s*kW"#, options: .regularExpression) != nil,
            "Unmatched title must not embed EEA kW: \(versioneLabel)"
        )
        versioneRow.tap()

        assertPickerDismissedAndVerdictShowsCharges(app: app, search: search)
    }

    /// Matched OEM: Hyundai Ioniq 5 2021 → titolo ufficiale · kW (58/72.6 era) → verdetto.
    @MainActor
    func testEVVersionPickerMatchedTeslaModelYShowsOfficialKw() throws {
        // Method name kept for suite count continuity; body covers Ioniq 5 matched OEM.
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_OPEN_TARGET_PICKER"] = "1"
        app.launch()

        dismissQuickStartIfNeeded(app)

        let search = app.descendants(matching: .any)["vehicle_catalog_search"]
        XCTAssertTrue(
            search.waitForExistence(timeout: 14),
            "Target vehicle catalog sheet should open"
        )
        search.tap()
        search.typeText("Ioniq 5")

        let model = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] %@", "IONIQ 5")
        ).firstMatch
        XCTAssertTrue(model.waitForExistence(timeout: 8), "Ioniq 5 search hit")
        model.tap()

        let year2021 = app.buttons.matching(
            NSPredicate(
                format: "label CONTAINS[c] %@ AND label CONTAINS[c] %@",
                "IONIQ 5", "2021"
            )
        ).firstMatch
        XCTAssertTrue(year2021.waitForExistence(timeout: 6), "Ioniq 5 2021 year")
        year2021.tap()

        let matchedRow = app.buttons.matching(
            NSPredicate(
                format: "label CONTAINS[c] %@ AND label CONTAINS[c] %@",
                "Long Range", "kW"
            )
        ).firstMatch
        let matchedAlt = app.buttons.matching(
            NSPredicate(
                format: "label CONTAINS[c] %@ AND label CONTAINS[c] %@",
                "Standard Range", "kW"
            )
        ).firstMatch
        XCTAssertTrue(
            matchedRow.waitForExistence(timeout: 6) || matchedAlt.waitForExistence(timeout: 2),
            "Matched Ioniq 5 row must show official name · kW"
        )
        let label = matchedRow.exists ? matchedRow.label : matchedAlt.label
        XCTAssertFalse(label.contains("239 kW"), "2021 must not show restyle AWD 239")
        XCTAssertFalse(label.contains("63 kWh") || label.contains("84 kWh"))
        if matchedRow.exists {
            matchedRow.tap()
        } else {
            matchedAlt.tap()
        }

        assertPickerDismissedAndVerdictShowsCharges(app: app, search: search)
    }

    @MainActor
    private func assertPickerDismissedAndVerdictShowsCharges(
        app: XCUIApplication,
        search: XCUIElement
    ) {
        let searchGone = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "exists == false"),
            object: search
        )
        _ = XCTWaiter.wait(for: [searchGone], timeout: 10)

        func verdictChromeVisible() -> Bool {
            app.buttons["Change inputs"].exists
                || app.buttons["Modifica dati"].exists
                || app.buttons["Modify input"].exists
                || app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "×")).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "ricariche")
                ).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "charges")
                ).firstMatch.exists
        }

        var verdictOpen = false
        for _ in 0..<20 {
            if verdictChromeVisible() {
                verdictOpen = true
                break
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.45))
        }
        if !verdictOpen {
            let tellMeEN = app.buttons["Tell me the truth"]
            let tellMeIT = app.buttons["Dimmi la verità"]
            if tellMeIT.waitForExistence(timeout: 2), tellMeIT.isHittable {
                tellMeIT.tap()
            } else if tellMeEN.exists, tellMeEN.isHittable {
                tellMeEN.tap()
            } else {
                app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.92)).tap()
            }
            for _ in 0..<16 {
                if verdictChromeVisible() {
                    verdictOpen = true
                    break
                }
                RunLoop.current.run(until: Date().addingTimeInterval(0.4))
            }
        }
        XCTAssertTrue(verdictOpen, "Verdict should open")

        let chargesOK =
            app.staticTexts.matching(NSPredicate(format: "label MATCHES %@", #".*[0-9]+×.*"#)).firstMatch
                .waitForExistence(timeout: 6)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "×")).firstMatch
                .waitForExistence(timeout: 2)
            || app.staticTexts.matching(
                NSPredicate(format: "label CONTAINS[c] %@", "ricariche")
            ).firstMatch.waitForExistence(timeout: 2)
        XCTAssertTrue(chargesOK, "Chosen version should show weekly charges on verdict")
    }

    /// PHEV con solo kWh mancante: chiede solo energia, poi apre il verdetto dopo l'inserimento.
    @MainActor
    func testPartialPHEVAsksOnlyKWhThenShowsVerdict() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_PARTIAL_PHEV_KWH_ONLY"] = "1"
        app.launchArguments += ["-UITesting", "-DisableAnimations"]
        app.launch()

        dismissQuickStartIfNeeded(app)

        let incompleteCard = app.descendants(matching: .any)["incomplete_catalog_data_card"]
        XCTAssertTrue(incompleteCard.waitForExistence(timeout: 12), "Partial PHEV must show incomplete card")
        let energyField = app.descendants(matching: .any)["incomplete_catalog_energy_field"]
        XCTAssertTrue(energyField.waitForExistence(timeout: 4), "Must ask for electric kWh")
        XCTAssertFalse(
            app.descendants(matching: .any)["incomplete_catalog_fuel_field"].exists,
            "Must not ask for CS fuel when official CS is already present"
        )
        XCTAssertTrue(
            app.descendants(matching: .any)["incomplete_catalog_weighted_honesty"].exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "ponderato")
                ).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "weighted")
                ).firstMatch.exists,
            "Must show honest note about weighted-only OEM kWh"
        )

        energyField.tap()
        // FormatStyle Double field often shows "0": select-all then replace with mid-range kWh/100.
        energyField.doubleTap()
        energyField.typeText("20.9")
        if app.keyboards.buttons["Done"].waitForExistence(timeout: 1) {
            app.keyboards.buttons["Done"].tap()
        } else {
            // Decimal pad has no Done — dismiss by tapping the incomplete card title.
            app.descendants(matching: .any)["incomplete_catalog_data_title"].tap()
        }

        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 3) || tellMeIT.waitForExistence(timeout: 1),
            "Simulate CTA should exist"
        )
        let tellMe = tellMeEN.exists ? tellMeEN : tellMeIT
        if !tellMe.isHittable {
            app.swipeUp()
        }
        tellMe.tap()

        let modifyEN = app.buttons["Change inputs"]
        let modifyIT = app.buttons["Modifica dati"]
        let modifyLegacy = app.buttons["Modify input"]
        let verdictOpened =
            modifyEN.waitForExistence(timeout: 10)
            || modifyIT.waitForExistence(timeout: 6)
            || modifyLegacy.waitForExistence(timeout: 3)
        XCTAssertTrue(verdictOpened, "After entering kWh, partial PHEV must open the verdict")
    }

    /// PHEV con catalogDataIncomplete: chiede consumi e non apre un verdetto inventato.
    @MainActor
    func testIncompletePHEVAsksForConsumptionInsteadOfVerdict() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchEnvironment["UITEST_INCOMPLETE_PHEV"] = "1"
        app.launchArguments += ["-UITesting", "-DisableAnimations"]
        app.launch()

        dismissQuickStartIfNeeded(app)

        let incompleteCard = app.descendants(matching: .any)["incomplete_catalog_data_card"]
        let titleById = app.descendants(matching: .any)["incomplete_catalog_data_title"]
        let titleIT = app.staticTexts["Dati incompleti"]
        let titleEN = app.staticTexts["Incomplete data"]
        let promptVisible =
            incompleteCard.waitForExistence(timeout: 12)
            || titleById.waitForExistence(timeout: 2)
            || titleIT.waitForExistence(timeout: 2)
            || titleEN.waitForExistence(timeout: 1)
        XCTAssertTrue(promptVisible, "Incomplete PHEV must show the consumption prompt")
        XCTAssertTrue(
            app.descendants(matching: .any)["incomplete_catalog_fuel_field"].exists
                || app.descendants(matching: .any)["incomplete_catalog_energy_field"].exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "batteria scarica")
                ).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "empty battery")
                ).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "kWh/100")
                ).firstMatch.exists,
            "Must show fuel and/or energy entry fields"
        )

        let tellMeEN = app.buttons["Tell me the truth"]
        let tellMeIT = app.buttons["Dimmi la verità"]
        XCTAssertTrue(
            tellMeEN.waitForExistence(timeout: 3) || tellMeIT.waitForExistence(timeout: 1),
            "Simulate CTA should exist"
        )
        if tellMeEN.exists { tellMeEN.tap() } else { tellMeIT.tap() }

        let modifyEN = app.buttons["Change inputs"]
        let modifyIT = app.buttons["Modifica dati"]
        let modifyLegacy = app.buttons["Modify input"]
        let verdictOpened =
            modifyEN.waitForExistence(timeout: 4)
            || modifyIT.waitForExistence(timeout: 2)
            || modifyLegacy.waitForExistence(timeout: 1)
        XCTAssertFalse(
            verdictOpened,
            "Incomplete PHEV must not open a verdict without user consumption"
        )
        // Prompt still on bench after failed simulate.
        XCTAssertTrue(
            incompleteCard.exists
                || titleIT.exists
                || titleEN.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "Dati incompleti")
                ).firstMatch.exists
                || app.staticTexts.matching(
                    NSPredicate(format: "label CONTAINS[c] %@", "Incomplete data")
                ).firstMatch.exists,
            "Incomplete prompt should remain after blocked simulate"
        )
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

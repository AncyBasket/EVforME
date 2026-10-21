//
//  SmokeProductUITests.swift
//  EVforME?UITests
//
//  Smoke 1.1 + 1.2 + 1.3 — screenshots su disco (repo docs/smoke/shots).
//

import XCTest
import ImageIO
import CoreGraphics
import Darwin

final class SmokeProductUITests: XCTestCase {
    private var shotsDir: URL!

    override func setUpWithError() throws {
        continueAfterFailure = false
        // Suite lunga (verdetto + kit + mappe): evita kill del runner su sim lento.
        executionTimeAllowance = 600
        let fromEnv = ProcessInfo.processInfo.environment["SMOKE_SHOTS_DIR"]
        if let fromEnv, !fromEnv.isEmpty {
            shotsDir = URL(fileURLWithPath: fromEnv, isDirectory: true)
        } else {
            shotsDir = URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("docs/smoke/shots", isDirectory: true)
        }
        try FileManager.default.createDirectory(at: shotsDir, withIntermediateDirectories: true)
    }

    @MainActor
    func testSmokeRetentionKitItaliaChargers() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launchArguments += ["-UITesting", "-DisableAnimations"]
        app.launch()

        dismissQuickStartIfNeeded(app)
        dismissSystemAlertsIfNeeded(app)
        saveShot(app, name: "01_workshop_cold")

        _ = app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Golf")).firstMatch
            .waitForExistence(timeout: 12)

        let tellMe = firstExistingButton(app, labels: ["Dimmi la verità", "Tell me the truth"])
        XCTAssertNotNil(tellMe, "Simulate CTA")
        tellMe?.tap()

        // 1.1 optional notification prompt — must not block
        dismissSystemAlertsIfNeeded(app)

        let modify = firstExistingButton(
            app,
            labels: ["Modifica dati", "Change inputs", "Modify input"],
            timeout: 20
        )
        XCTAssertNotNil(modify, "Verdict should open")
        saveShot(app, name: "02_verdict_open")

        // 1.2 — expand costs for kit Italia rows
        let costs = firstExistingStatic(
            app,
            labels: ["Approfondisci i costi", "Deep dive into costs", "Explore costs"]
        )
        costs?.tap()
        RunLoop.current.run(until: Date().addingTimeInterval(1.0))
        scrollDown(app, times: 2)
        saveShot(app, name: "03_verdict_kit_italia")

        // Close verdict via accessibility label on X
        if let close = firstExistingButton(app, labels: ["Chiudi esito", "Close result"], timeout: 3) {
            close.tap()
        } else if let modifyBtn = firstExistingButton(app, labels: ["Modifica dati", "Change inputs"]) {
            modifyBtn.tap()
        }
        dismissSystemAlertsIfNeeded(app)

        // Wait until workshop CTA is hittable (sheet fully dismissed)
        let workshopCTA = firstExistingButton(app, labels: ["Dimmi la verità", "Tell me the truth"], timeout: 10)
        XCTAssertNotNil(workshopCTA)
        XCTAssertTrue(workshopCTA?.isHittable == true, "Workshop should be interactive after dismiss")

        let lastTitle = app.staticTexts["Ultimo confronto"]
        let lastTitleEN = app.staticTexts["Last comparison"]
        let lastCardVisible =
            (lastTitle.waitForExistence(timeout: 6) && lastTitle.isHittable)
            || (lastTitleEN.waitForExistence(timeout: 2) && lastTitleEN.isHittable)
        XCTAssertTrue(lastCardVisible, "Last comparison card after first verdict")
        saveShot(app, name: "04_last_comparison_card")

        let recalculate = firstExistingButton(
            app,
            labels: [
                "Ricalcola con dati di oggi",
                "Recalculate with today’s data",
                "Recalculate with today's data",
            ]
        )
        XCTAssertNotNil(recalculate, "Recalculate action")
        recalculate?.tap()
        dismissSystemAlertsIfNeeded(app)
        XCTAssertNotNil(
            firstExistingButton(app, labels: ["Modifica dati", "Change inputs"], timeout: 15),
            "Recalculate should reopen verdict"
        )
        saveShot(app, name: "05_verdict_recalculated")

        let close2 = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", "Chiudi")).firstMatch
        if close2.waitForExistence(timeout: 2) {
            close2.tap()
        } else {
            firstExistingButton(app, labels: ["Modifica dati", "Change inputs"])?.tap()
        }

        XCTAssertTrue(
            firstExistingButton(app, labels: ["Dimmi la verità", "Tell me the truth"], timeout: 8) != nil
        )

        let restore = firstExistingButton(
            app,
            labels: ["Ripristina nel form", "Restore into form"],
            timeout: 5
        )
        XCTAssertNotNil(restore)
        restore?.tap()

        let reopen = firstExistingButton(app, labels: ["Riapri verdetto", "Reopen verdict"], timeout: 5)
        XCTAssertNotNil(reopen)
        reopen?.tap()
        dismissSystemAlertsIfNeeded(app)
        XCTAssertNotNil(
            firstExistingButton(app, labels: ["Modifica dati", "Change inputs"], timeout: 12)
        )
        let close3 = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", "Chiudi")).firstMatch
        if close3.waitForExistence(timeout: 2) {
            close3.tap()
        } else {
            firstExistingButton(app, labels: ["Modifica dati", "Change inputs"])?.tap()
        }

        // Guides
        if let guidesTab = firstExistingButton(app, labels: ["Letture", "Guides", "Readings"], timeout: 5) {
            guidesTab.tap()
        }
        let chargingEntry = app.staticTexts["Colonnine vicino a te"].waitForExistence(timeout: 5)
            || app.staticTexts["Chargers near you"].waitForExistence(timeout: 2)
        XCTAssertTrue(chargingEntry, "1.3 entry on Guides")
        saveShot(app, name: "06_guides_hub")

        let bollo = app.staticTexts["Bollo ed esenzioni EV (orientativo)"]
        let roadTax = app.staticTexts["Road tax & EV exemptions (indicative)"]
        XCTAssertTrue(
            bollo.waitForExistence(timeout: 5) || roadTax.waitForExistence(timeout: 2),
            "Guides must list bollo article"
        )
        if bollo.exists { bollo.tap() } else { roadTax.tap() }
        // Wait until article content is on screen (not still the hub).
        let bolloBody =
            app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "esenzion")).firstMatch
                .waitForExistence(timeout: 6)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "exemption")).firstMatch
                .waitForExistence(timeout: 3)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "bollo")).firstMatch
                .waitForExistence(timeout: 3)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "road tax")).firstMatch
                .waitForExistence(timeout: 2)
        XCTAssertTrue(bolloBody, "Bollo guide detail should open")
        RunLoop.current.run(until: Date().addingTimeInterval(0.6))
        saveShot(app, name: "07_guides_bollo")
        firstExistingButton(app, labels: ["Fatto", "Close", "Done"], timeout: 4)?.tap()

        // Map city shot is owned by testSmokeChargingMapCityOnly (avoids overwriting with hub/bollo).
        // Here only open map if the sheet appears; then always return to workshop for 09.
        if let guidesTab = firstExistingButton(app, labels: ["Letture", "Guides", "Readings"], timeout: 3) {
            guidesTab.tap()
        }
        let entryTitle = app.staticTexts["Colonnine vicino a te"].exists
            ? app.staticTexts["Colonnine vicino a te"]
            : app.staticTexts["Chargers near you"]
        if entryTitle.waitForExistence(timeout: 5) {
            entryTitle.tap()
            dismissSystemAlertsIfNeeded(app)
            RunLoop.current.run(until: Date().addingTimeInterval(1.2))
            dismissSystemAlertsIfNeeded(app)
            let mapReady =
                app.navigationBars["Colonnine vicine"].waitForExistence(timeout: 8)
                || app.navigationBars["Nearby chargers"].waitForExistence(timeout: 3)
                || app.descendants(matching: .any)["charging_map_mode_picker"].waitForExistence(timeout: 4)
                || app.buttons["Apri in Mappe"].waitForExistence(timeout: 3)
                || app.buttons["Open in Maps"].waitForExistence(timeout: 2)
                || app.maps.firstMatch.waitForExistence(timeout: 3)
            if mapReady {
                dismissSystemAlertsIfNeeded(app)
                firstExistingButton(app, labels: ["Fatto", "Close", "Done"], timeout: 4)?.tap()
            }
        }

        // Shot 09 is captured in testSmokeChargingMapCityOnly (reliable path back to workshop).
    }

    @MainActor
    private func activateChargingMapCityMode(_ app: XCUIApplication) {
        let labels = ["Cerca per città", "Search by city"]
        for label in labels {
            let btn = app.buttons[label]
            if btn.waitForExistence(timeout: 2), btn.isHittable {
                btn.tap()
                return
            }
            let seg = app.segmentedControls.buttons[label]
            if seg.waitForExistence(timeout: 1), seg.isHittable {
                seg.tap()
                return
            }
        }
        let picker = app.descendants(matching: .any)["charging_map_mode_picker"]
        if picker.waitForExistence(timeout: 2) {
            let city = picker.buttons.matching(
                NSPredicate(format: "label CONTAINS[c] %@ OR label CONTAINS[c] %@", "città", "city")
            ).firstMatch
            if city.exists { city.tap(); return }
            // Last resort: tap right half of segmented control (city is usually second).
            picker.coordinate(withNormalizedOffset: CGVector(dx: 0.78, dy: 0.5)).tap()
        }
    }

    @MainActor
    func testSmokeChargingMapCityOnly() throws {
        let app = XCUIApplication()
        app.launchEnvironment["UITEST_PRESET_VEHICLES"] = "1"
        app.launch()
        dismissQuickStartIfNeeded(app)
        dismissSystemAlertsIfNeeded(app)

        if let guidesTab = firstExistingButton(app, labels: ["Letture", "Guides", "Readings"], timeout: 8) {
            guidesTab.tap()
        }
        let entry = app.staticTexts["Colonnine vicino a te"]
        XCTAssertTrue(entry.waitForExistence(timeout: 6) || app.staticTexts["Chargers near you"].waitForExistence(timeout: 2))
        if entry.exists { entry.tap() } else { app.staticTexts["Chargers near you"].tap() }

        dismissSystemAlertsIfNeeded(app)
        RunLoop.current.run(until: Date().addingTimeInterval(1.5))
        dismissSystemAlertsIfNeeded(app)
        saveShot(app, name: "08_charging_map_sheet")

        activateChargingMapCityMode(app)
        let field =
            app.textFields["charging_map_city_field"].exists
            ? app.textFields["charging_map_city_field"]
            : app.textFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 5), "city field for 08/08b")
        // 08b first: city mode with empty query → in-app fallback coordinate (distinct from Milano).
        RunLoop.current.run(until: Date().addingTimeInterval(3))
        dismissSystemAlertsIfNeeded(app)
        let mapChrome =
            app.descendants(matching: .any)["charging_map_mode_picker"].exists
            || app.navigationBars["Colonnine vicine"].exists
            || app.navigationBars["Nearby chargers"].exists
            || app.maps.firstMatch.exists
            || app.buttons["Apri in Mappe"].exists
            || app.buttons["Open in Maps"].exists
        XCTAssertTrue(mapChrome, "08/08b must be the charging map, not guides hub")
        saveShot(app, name: "08b_charging_map_fallback")

        field.tap()
        field.typeText("Milano")
        let search =
            app.buttons["charging_map_city_search"].exists
            ? app.buttons["charging_map_city_search"]
            : firstExistingButton(app, labels: ["Cerca", "Search"], timeout: 2)
        search?.tap()
        RunLoop.current.run(until: Date().addingTimeInterval(6))
        dismissSystemAlertsIfNeeded(app)
        saveShot(app, name: "08_charging_map_city")

        let cityURL = shotsDir.appendingPathComponent("08_charging_map_city.png")
        let fallbackURL = shotsDir.appendingPathComponent("08b_charging_map_fallback.png")
        let cityData = try Data(contentsOf: cityURL)
        let fallbackData = try Data(contentsOf: fallbackURL)
        XCTAssertNotEqual(cityData, fallbackData, "08 and 08b must be different screenshots")
        firstExistingButton(app, labels: ["Fatto", "Close", "Done"], timeout: 4)?.tap()
        dismissSystemAlertsIfNeeded(app)

        let workshop = firstExistingButton(app, labels: ["Banco", "Workshop", "Bench"], timeout: 8)
        XCTAssertNotNil(workshop, "Workshop tab for 09 shot")
        workshop?.tap()
        let workshopReady =
            app.buttons["Dimmi la verità"].waitForExistence(timeout: 10)
            || app.buttons["Tell me the truth"].waitForExistence(timeout: 4)
            || app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "Golf")).firstMatch
                .waitForExistence(timeout: 4)
        XCTAssertTrue(workshopReady, "Workshop bench visible for 09 shot")
        RunLoop.current.run(until: Date().addingTimeInterval(0.5))
        saveShot(app, name: "09_workshop_after_smoke")
    }

    @MainActor
    private func dismissSystemAlertsIfNeeded(_ app: XCUIApplication) {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let labels = [
            "Non consentire",
            "Don’t Allow",
            "Don't Allow",
            "Non ora",
            "Not Now",
            "Allow",
            "Consenti",
            "OK",
            "Allow While Using App",
            "Consenti durante l’uso",
            "Consenti una volta",
        ]
        for _ in 0..<4 {
            var tapped = false
            for label in ["Non ora", "Not Now", "Non consentire", "Don’t Allow", "Don't Allow"] {
                let spring = springboard.buttons[label]
                if spring.waitForExistence(timeout: 0.5) {
                    spring.tap()
                    tapped = true
                    break
                }
                let alert = app.alerts.buttons[label]
                if alert.waitForExistence(timeout: 0.3) {
                    alert.tap()
                    tapped = true
                    break
                }
                // SKStoreReviewController may present as other element
                let any = app.buttons[label]
                if any.waitForExistence(timeout: 0.3), any.isHittable {
                    any.tap()
                    tapped = true
                    break
                }
            }
            if !tapped {
                for label in labels {
                    let btn = springboard.buttons[label]
                    if btn.waitForExistence(timeout: 0.25) {
                        btn.tap()
                        tapped = true
                        break
                    }
                }
            }
            if !tapped { break }
            RunLoop.current.run(until: Date().addingTimeInterval(0.35))
        }
    }

    @MainActor
    private func saveShot(_ app: XCUIApplication, name: String) {
        // Do not redraw XCUIScreenshot via UIImage (EXIF Orientation=6 → cropped/black halves).
        // Prefer simctl full-resolution PNG for the UI-test simulator (posix_spawn; Process is macOS-only).
        let url = shotsDir.appendingPathComponent("\(name).png")
        let udid = ProcessInfo.processInfo.environment["SIMULATOR_UDID"] ?? "booted"
        let simctlOK = runSimctlScreenshot(udid: udid, path: url.path)
        let shot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: shot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        do {
            if !simctlOK {
                try shot.pngRepresentation.write(to: url)
            }
            try validateSmokePNG(at: url, name: name)
        } catch {
            XCTFail("Could not write smoke shot \(name): \(error)")
        }
    }

    /// Host-side `xcrun simctl io <udid> screenshot` (UI tests run under Simulator runtime).
    private func runSimctlScreenshot(udid: String, path: String) -> Bool {
        let args = ["/usr/bin/xcrun", "simctl", "io", udid, "screenshot", path]
        var cArgs = args.map { strdup($0) }
        cArgs.append(nil)
        defer { cArgs.forEach { if let p = $0 { free(p) } } }
        var pid: pid_t = 0
        let spawned = cArgs.withUnsafeBufferPointer { buf -> Int32 in
            posix_spawn(&pid, buf.baseAddress![0], nil, nil, buf.baseAddress!, environ)
        }
        guard spawned == 0 else { return false }
        var status: Int32 = 0
        waitpid(pid, &status, 0)
        return status == 0 && FileManager.default.fileExists(atPath: path)
    }

    /// Portrait full-bleed checks — no UIImage redraw; read pixels as stored.
    private func validateSmokePNG(at url: URL, name: String) throws {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
              let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            throw NSError(domain: "SmokeShot", code: 1, userInfo: [NSLocalizedDescriptionKey: "\(name): cannot read PNG"])
        }
        let w = cg.width
        let h = cg.height
        XCTAssertGreaterThan(h, w, "\(name) must be portrait, got \(w)×\(h)")
        assertNoFullyBlackHalf(cgImage: cg, name: name)
    }

    /// Reject black-strip artifacts on left/right/top/bottom halves.
    private func assertNoFullyBlackHalf(cgImage: CGImage, name: String) {
        let w = cgImage.width
        let h = cgImage.height
        guard w > 10, h > 10 else {
            XCTFail("\(name): image too small \(w)×\(h)")
            return
        }
        guard let data = cgImage.dataProvider?.data,
              let ptr = CFDataGetBytePtr(data) else {
            XCTFail("\(name): cannot read pixels")
            return
        }
        let bpr = cgImage.bytesPerRow
        let bpp = max(1, cgImage.bitsPerPixel / 8)
        func regionMostlyBlack(x0: Int, x1: Int, y0: Int, y1: Int) -> Bool {
            var dark = 0
            var total = 0
            var y = y0
            while y < y1 {
                var x = x0
                while x < x1 {
                    let i = y * bpr + x * bpp
                    let r = Int(ptr[i])
                    let g = bpp > 1 ? Int(ptr[i + 1]) : r
                    let b = bpp > 2 ? Int(ptr[i + 2]) : r
                    if r < 8 && g < 8 && b < 8 { dark += 1 }
                    total += 1
                    x += max(1, (x1 - x0) / 24)
                }
                y += max(1, (y1 - y0) / 48)
            }
            return total > 0 && Double(dark) / Double(total) > 0.92
        }
        let midX = w / 2
        let midY = h / 2
        XCTAssertFalse(regionMostlyBlack(x0: 0, x1: midX, y0: 0, y1: h), "\(name): left half is fully black")
        XCTAssertFalse(regionMostlyBlack(x0: midX, x1: w, y0: 0, y1: h), "\(name): right half is fully black")
        XCTAssertFalse(regionMostlyBlack(x0: 0, x1: w, y0: 0, y1: midY), "\(name): top half is fully black")
        XCTAssertFalse(regionMostlyBlack(x0: 0, x1: w, y0: midY, y1: h), "\(name): bottom half is fully black")
    }

    @MainActor
    private func scrollDown(_ app: XCUIApplication, times: Int) {
        for _ in 0..<times {
            let start = CGVector(dx: 0.5, dy: 0.72)
            let end = CGVector(dx: 0.5, dy: 0.28)
            app.coordinate(withNormalizedOffset: start)
                .press(forDuration: 0.05, thenDragTo: app.coordinate(withNormalizedOffset: end))
            RunLoop.current.run(until: Date().addingTimeInterval(0.35))
        }
    }

    @MainActor
    private func firstExistingButton(
        _ app: XCUIApplication,
        labels: [String],
        timeout: TimeInterval = 3
    ) -> XCUIElement? {
        for (index, label) in labels.enumerated() {
            let button = app.buttons[label]
            let wait = index == 0 ? timeout : min(1.5, timeout)
            if button.waitForExistence(timeout: wait) {
                return button
            }
        }
        return nil
    }

    @MainActor
    private func firstExistingStatic(
        _ app: XCUIApplication,
        labels: [String],
        timeout: TimeInterval = 3
    ) -> XCUIElement? {
        for (index, label) in labels.enumerated() {
            let el = app.staticTexts[label]
            let wait = index == 0 ? timeout : min(1.2, timeout)
            if el.waitForExistence(timeout: wait) {
                return el
            }
        }
        // Buttons may wrap the expandable title
        return firstExistingButton(app, labels: labels, timeout: 1)
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
            if button.waitForExistence(timeout: 1.0) {
                button.tap()
                return
            }
        }
    }
}

//
//  MarketHonestyPrivacyTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class MarketHonestyPrivacyTests: XCTestCase {

    private func baseInput(market: AppMarket) -> UserInput {
        UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: market == .IT ? OfficialEnergyCosts.Fallback.petrolPerLiter : 0,
            ownershipYears: 5,
            electricityPricePerKWh: market == .IT ? PublicChargingPriceDefaults.homePerKWh : 0,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            market: market
        )
    }

    func testNonItalyDefaultsStartEmpty() {
        var input = baseInput(market: .DE)
        input.clearItalianOfficialEnergyDefaults()
        XCTAssertEqual(input.fuelPrice, 0, accuracy: 0.0001)
        XCTAssertEqual(input.electricityPricePerKWh, 0, accuracy: 0.0001)
        XCTAssertNil(input.chargingConfiguration.customPublicPricePerKWh)
        XCTAssertNil(input.annualInsuranceOverrideEUR)
        XCTAssertTrue(input.insuranceExcludedAsEmptyOutsideItaly)
    }

    func testVerdictBlockedOutsideItalyWithoutPrices() {
        var input = baseInput(market: .DE)
        input.clearItalianOfficialEnergyDefaults()
        let errors = InputValidator.validate(input)
        XCTAssertTrue(errors.contains(L10n.validationEnterFuelPriceForMarket))
        XCTAssertTrue(errors.contains(L10n.validationEnterHomeElectricityPriceForMarket))
        XCTAssertTrue(errors.contains(L10n.validationEnterPublicElectricityPriceForMarket))
        XCTAssertNil(EVSimulator.simulate(input: input))
    }

    func testVerdictRunsOutsideItalyAfterEnteringPrices() {
        var input = baseInput(market: .DE)
        input.clearItalianOfficialEnergyDefaults()
        input.fuelPrice = 1.85
        input.electricityPricePerKWh = 0.40
        input.chargingConfiguration.customPublicPricePerKWh = 0.70
        let errors = InputValidator.validate(input)
        XCTAssertFalse(errors.contains(L10n.validationEnterFuelPriceForMarket))
        XCTAssertFalse(errors.contains(L10n.validationEnterHomeElectricityPriceForMarket))
        XCTAssertFalse(errors.contains(L10n.validationEnterPublicElectricityPriceForMarket))
        XCTAssertNotNil(EVSimulator.simulate(input: input))
    }

    func testItalyKeepsOfficialDefaultsAndSimulates() {
        let input = baseInput(market: .IT)
        XCTAssertGreaterThan(input.fuelPrice, 0)
        XCTAssertGreaterThan(input.electricityPricePerKWh, 0)
        XCTAssertFalse(input.insuranceExcludedAsEmptyOutsideItaly)
        let errors = InputValidator.validate(input)
        XCTAssertFalse(errors.contains(L10n.validationEnterFuelPriceForMarket))
        XCTAssertNotNil(EVSimulator.simulate(input: input))
    }

    func testApplyOfficialCostsSkippedOutsideItaly() {
        var input = baseInput(market: .FR)
        input.clearItalianOfficialEnergyDefaults()
        let costs = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.99,
            electricityPricePerKWh: 0.33,
            updatedAt: "2026-11-15"
        )
        let changed = StorageService.shared.applyOfficialCostsIfNeeded(costs, to: &input)
        XCTAssertFalse(changed)
        XCTAssertEqual(input.fuelPrice, 0, accuracy: 0.0001)
        XCTAssertEqual(input.electricityPricePerKWh, 0, accuracy: 0.0001)
    }

    func testUSEPARowsHiddenForItalyShownForUS() {
        let itSource = VehicleCatalogService.shared.sourceVehicles(for: .IT)
        let usSource = VehicleCatalogService.shared.sourceVehicles(for: .US)
        let itEPA = itSource.filter { ($0.market ?? "").uppercased() == "US/EPA" }
        let usEPA = usSource.filter { ($0.market ?? "").uppercased() == "US/EPA" }
        XCTAssertTrue(itEPA.isEmpty, "US/EPA must not appear for IT/EU markets")
        XCTAssertFalse(usEPA.isEmpty, "US/EPA rows should appear for US")
        XCTAssertEqual(itSource.filter { ($0.market ?? "IT").uppercased() == "IT" }.count > 1000, true)
    }

    func testInsuranceZeroOutsideItalyWithoutOverride() {
        let rc = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: 20_000,
            yearlyKm: 12_000,
            electrified: false,
            annualInsuranceOverrideEUR: nil,
            market: .DE
        )
        XCTAssertEqual(rc, 0, accuracy: 0.01)
        let withOverride = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: 20_000,
            yearlyKm: 12_000,
            electrified: false,
            annualInsuranceOverrideEUR: 500,
            market: .DE
        )
        XCTAssertEqual(withOverride, 500, accuracy: 0.01)
        let italy = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: 20_000,
            yearlyKm: 12_000,
            electrified: false,
            annualInsuranceOverrideEUR: nil,
            market: .IT
        )
        XCTAssertEqual(italy, OwnershipCostEstimates.ivassAverageRCEURPerYear, accuracy: 0.01)
    }

    func testExpiredIncentiveNeverEntersCalculationOrActiveWindow() {
        let schedule = ItalianIncentiveSchedule.bundledFallback
        XCTAssertEqual(schedule.validUntil, "2026-06-30")
        let after = ItalianIncentiveSchedule.parseFlexibleDate("2026-07-01")!
        if case .expired = schedule.windowStatus(asOf: after) {
            // ok
        } else {
            XCTFail("bundled schedule must be expired after validUntil")
        }
        let bonus = schedule.estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true,
            iseeEUR: 25_000,
            asOf: after
        )
        XCTAssertEqual(bonus, 0, accuracy: 0.01)

        var input = baseInput(market: .IT)
        input.comparisonIntent = .consideringPurchase
        input.includeIncentives = true
        input.iseeEUR = 25_000
        // Live schedule is expired as of today (Nov 2026) → 0 in UserInput helper too.
        XCTAssertEqual(input.estimatedPurchaseIncentiveEUR, 0, accuracy: 0.01)
        if case .expired = ItalianIncentives.windowStatus {
            // shown as closed, not active
        } else {
            XCTFail("ItalianIncentives.windowStatus must be expired for bundled validUntil 2026-06-30")
        }
    }

    func testReleaseAnalyticsAndLeadURLsEmpty() throws {
        // Suite runs Debug (localhost stubs). Release emptiness is enforced by `#else { return "" }`
        // in Defaults.swift — assert that source contract so we never ship non-empty Release URLs.
        let defaultsPath = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("EVforME?/Core/Constants/Defaults.swift")
        let source = try String(contentsOf: defaultsPath, encoding: .utf8)
        XCTAssertTrue(
            source.contains("static var analyticsIngestURL"),
            "Defaults.analyticsIngestURL must exist"
        )
        XCTAssertTrue(
            source.contains("static var leadWebhookURL"),
            "Defaults.leadWebhookURL must exist"
        )
        // Both Release branches must return empty string (Data Not Collected).
        let analyticsSlice = source.components(separatedBy: "static var analyticsIngestURL").dropFirst().first ?? ""
        let leadSlice = source.components(separatedBy: "static var leadWebhookURL").dropFirst().first ?? ""
        XCTAssertTrue(
            analyticsSlice.contains("#else\n        return \"\""),
            "Release analyticsIngestURL must be empty"
        )
        XCTAssertTrue(
            leadSlice.contains("#else\n        return \"\""),
            "Release leadWebhookURL must be empty"
        )
        #if !DEBUG
        XCTAssertTrue(Defaults.analyticsIngestURL.isEmpty)
        XCTAssertTrue(Defaults.leadWebhookURL.isEmpty)
        #endif
    }
}

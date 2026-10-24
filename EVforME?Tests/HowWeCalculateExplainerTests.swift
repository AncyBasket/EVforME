//
//  HowWeCalculateExplainerTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class HowWeCalculateExplainerTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        // Pin calendar year so horizon averages (e.g. Lazio EV ≈ 56,80) stay stable past 2026.
        Defaults.referenceCalendarYearProvider = { 2026 }
    }

    override func tearDown() {
        Defaults.referenceCalendarYearProvider = {
            Calendar.current.component(.year, from: Date())
        }
        super.tearDown()
    }

    func testFuelFromCO2Constants_MatchPythonScriptCoefficientsViaFilePath() throws {
        let scriptURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("scripts/fill_catalog_fuels_from_eea.py")
        XCTAssertTrue(FileManager.default.fileExists(atPath: scriptURL.path), scriptURL.path)
        let text = try String(contentsOf: scriptURL, encoding: .utf8)

        func requireDouble(_ name: String) throws -> Double {
            let pattern = #"\#(name)\s*=\s*([0-9]+(?:\.[0-9]+)?)"#
            let re = try NSRegularExpression(pattern: pattern)
            let range = NSRange(text.startIndex..<text.endIndex, in: text)
            guard let match = re.firstMatch(in: text, range: range),
                  let valueRange = Range(match.range(at: 1), in: text),
                  let value = Double(text[valueRange]) else {
                XCTFail("Missing \(name) in \(scriptURL.lastPathComponent)")
                return .nan
            }
            return value
        }

        XCTAssertEqual(try requireDouble("C_PETROL"), FuelFromCO2Constants.cPetrol, accuracy: 1e-12)
        XCTAssertEqual(try requireDouble("C_DIESEL"), FuelFromCO2Constants.cDiesel, accuracy: 1e-12)
        XCTAssertEqual(try requireDouble("D_PETROL"), FuelFromCO2Constants.dPetrolKgPerL, accuracy: 1e-12)
        XCTAssertEqual(try requireDouble("D_DIESEL"), FuelFromCO2Constants.dDieselKgPerL, accuracy: 1e-12)
        XCTAssertEqual(try requireDouble("CO2_FACTOR"), FuelFromCO2Constants.co2Factor, accuracy: 1e-12)
    }

    func testLitersPer100km_OnlyPetrolDiesel() {
        XCTAssertNotNil(FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .petrol))
        XCTAssertNotNil(FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .diesel))
        XCTAssertNil(FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .lpg))
        XCTAssertNil(FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .cng))
        XCTAssertNil(FuelFromCO2Constants.litersPer100km(fromCO2GramsPerKm: 120, fuelKind: .unknown))
    }

    func testBolloTariffs_MatchCalculationGetters() throws {
        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .molise)), 2.76, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .lazio)), 2.84, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .lombardia)), 0, accuracy: 1e-9)
        XCTAssertTrue(ItalianRegion.lombardia.evPermanentlyExempt)

        XCTAssertEqual(
            try XCTUnwrap(HowWeCalculateExplainer.evBolloEURPerKw(for: .unspecified)),
            OwnershipCostEstimates.nationalEVBolloEURPerKw,
            accuracy: 1e-9
        )
        XCTAssertTrue(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .unspecified))
        XCTAssertFalse(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .molise))
        XCTAssertFalse(HowWeCalculateExplainer.usesNationalEVBolloEstimate(for: .lazio))
    }

    func testSuperbolloConstants_MatchItalianRegion() {
        XCTAssertEqual(HowWeCalculateExplainer.superbolloThresholdKw, 185, accuracy: 1e-9)
        XCTAssertEqual(HowWeCalculateExplainer.superbolloEURPerKwAboveThreshold, 20, accuracy: 1e-9)
        let sb = ItalianRegion.nationalSuperbolloEUR(powerKw: 200, vehicleYear: 2024, referenceYear: 2026)
        XCTAssertEqual(sb, 20 * (200 - 185), accuracy: 1e-9)
    }

    func testConfidenceBands() {
        XCTAssertEqual(ConfidenceBand.from(score: nil), .unknown)
        XCTAssertEqual(ConfidenceBand.from(score: 0.9), .high)
        XCTAssertEqual(ConfidenceBand.from(score: 0.8), .high)
        XCTAssertEqual(ConfidenceBand.from(score: 0.5), .medium)
        XCTAssertEqual(ConfidenceBand.from(score: 0.49), .low)
    }

    func testConsumptionSourceCategory_Mapping() {
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "seed+EEA-WLTP"),
            .eeaWLTP
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "EEA co2cars IT 2024 n=272"),
            .eeaWLTP
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "seed+EEA-NEDC"),
            .eeaNEDC
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "EEA co2cars IT 2017 n=80;NEDC"),
            .eeaNEDC
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(
                from: "seed+EEA-NEDC",
                vehicleYear: 2008
            ),
            .estimate,
            "Pre-2010 must not be categorized as EEA"
        )
        XCTAssertNil(
            HowWeCalculateExplainer.sourceURL(
                from: "stima (pre-2010; dati consumi non da co2cars IT)",
                category: .estimate
            )
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "EPA-FuelEconomy"),
            .epaUSA
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "IT-listino-600e-WLTP~15.8"),
            .manufacturer
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(
                from: "IT-listino-GrandePanda-EV-WLTP~15.5"
            ),
            .manufacturer,
            "GrandePanda must not match substring 'epa'"
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(
                from: "BMW press tech data — https://www.press.bmwgroup.com/x"
            ),
            .manufacturer
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "seed+EEA-WLTP+stima(da EEA IT 2024)"),
            .estimate
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: nil),
            .unknown
        )
    }

    func testLooksLikeEPASource_TokenNotSubstring() {
        XCTAssertTrue(HowWeCalculateExplainer.looksLikeEPASource("EPA-FuelEconomy"))
        XCTAssertTrue(HowWeCalculateExplainer.looksLikeEPASource("source epa fuel"))
        XCTAssertTrue(HowWeCalculateExplainer.looksLikeEPASource("https://www.fueleconomy.gov/feg/"))
        XCTAssertFalse(HowWeCalculateExplainer.looksLikeEPASource("IT-listino-GrandePanda-EV-WLTP~15.5"))
        XCTAssertFalse(HowWeCalculateExplainer.looksLikeEPASource("IT-listino-GrandePanda-HEV-WLTP"))
    }

    func testSourceURL_EEAAndEPADefaults_AndEmbedded() {
        XCTAssertEqual(
            HowWeCalculateExplainer.sourceURL(from: "seed+EEA-WLTP"),
            OfficialLinks.eeaCO2CarsDataset
        )
        XCTAssertEqual(
            HowWeCalculateExplainer.sourceURL(from: "EPA-FuelEconomy"),
            OfficialLinks.epaFuelEconomy
        )
        let embedded = HowWeCalculateExplainer.sourceURL(
            from: "EEA CO2→FC — https://www.eea.europa.eu/data-and-maps"
        )
        XCTAssertEqual(embedded?.host, "www.eea.europa.eu")
        XCTAssertNil(HowWeCalculateExplainer.sourceURL(from: "scheda costruttore senza url"))
        XCTAssertEqual(
            HowWeCalculateExplainer.consumptionSourceCategory(from: "scheda costruttore senza url"),
            .manufacturer
        )
    }

    func testFuelLikelyFromCO2_NeverForBEV() throws {
        let tesla = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2020"))
        XCTAssertEqual(tesla.powertrain, .ev)
        XCTAssertTrue((tesla.sourceName ?? "").localizedCaseInsensitiveContains("eea"))
        XCTAssertFalse(
            HowWeCalculateExplainer.fuelLikelyFromCO2(
                sourceName: tesla.sourceName,
                powertrain: tesla.powertrain
            )
        )

        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2020",
            italianRegion: .lazio
        )
        let model = HowWeCalculateExplainer.makeModel(userInput: input, referenceYear: 2026)
        let target = try XCTUnwrap(model.target)
        XCTAssertFalse(target.showsCO2ToFuelNote, "BEV must not show CO₂→L/100 note")
        XCTAssertEqual(target.sourceCategory, .eeaWLTP)
    }

    func testFuelLikelyFromCO2_ICEWithEEA() throws {
        let golf = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-2020"))
        XCTAssertEqual(golf.powertrain, .ice)
        XCTAssertTrue(
            HowWeCalculateExplainer.fuelLikelyFromCO2(
                sourceName: golf.sourceName,
                powertrain: golf.powertrain
            )
        )
        XCTAssertFalse(
            HowWeCalculateExplainer.fuelLikelyFromCO2(
                sourceName: "Manufacturer WLTP sheet",
                powertrain: .ice
            )
        )
    }

    func testBolloPathAndAmount_MatchBolloPerYearDetail_MoliseAndLazio() throws {
        let thermal = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-2020"))
        let ev = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2020"))
        XCTAssertEqual(thermal.powertrain, .ice)
        XCTAssertEqual(ev.powertrain, .ev)

        // Molise thermal with high kW → regional + superbollo applied.
        let moliseThermal = HowWeCalculateExplainer.bolloDetail(
            vehicle: thermal,
            bookletKw: 200,
            region: .molise,
            referenceYear: 2026,
            ownershipYears: 5
        )
        let moliseThermalThisYear = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: thermal.taxesPerYear,
            powertrain: thermal.powertrain,
            vehicleYear: thermal.year,
            referenceYear: 2026,
            bookletPowerKwP2: 200,
            italianRegion: .molise,
            fuelKind: thermal.resolvedFuelKind,
            catalogPowerKw: thermal.powerKw
        )
        XCTAssertEqual(moliseThermal.thisYearEUR, moliseThermalThisYear.amount, accuracy: 1e-9)
        if case .thermalRegional(let showsSuperbollo) = moliseThermal.path {
            XCTAssertTrue(showsSuperbollo)
        } else {
            XCTFail("Expected thermalRegional for Molise ICE with 200 kW, got \(moliseThermal.path)")
        }

        // Molise thermal under 185 kW → regional, no superbollo row.
        let moliseLow = HowWeCalculateExplainer.bolloDetail(
            vehicle: thermal,
            bookletKw: 100,
            region: .molise,
            referenceYear: 2026,
            ownershipYears: 5
        )
        if case .thermalRegional(let showsSuperbollo) = moliseLow.path {
            XCTAssertFalse(showsSuperbollo)
        } else {
            XCTFail("Expected thermalRegional without superbollo, got \(moliseLow.path)")
        }

        // Lazio thermal → catalog estimate (no regional thermal tariff).
        let lazioThermal = HowWeCalculateExplainer.bolloDetail(
            vehicle: thermal,
            bookletKw: 100,
            region: .lazio,
            referenceYear: 2026,
            ownershipYears: 5
        )
        XCTAssertEqual(lazioThermal.path, .thermalCatalogEstimate)
        XCTAssertEqual(lazioThermal.thisYearEUR, thermal.taxesPerYear, accuracy: 1e-9)
        XCTAssertEqual(lazioThermal.averageEUR, thermal.taxesPerYear, accuracy: 1e-9)

        // Molise EV post-esenzione with P.2 → quarter rate, never superbollo.
        let moliseEV = HowWeCalculateExplainer.bolloDetail(
            vehicle: ev,
            bookletKw: 100,
            region: .molise,
            referenceYear: 2026,
            ownershipYears: 5
        )
        let moliseEVThisYear = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: ev.taxesPerYear,
            powertrain: ev.powertrain,
            vehicleYear: ev.year,
            referenceYear: 2026,
            bookletPowerKwP2: 100,
            italianRegion: .molise,
            fuelKind: ev.resolvedFuelKind,
            catalogPowerKw: nil
        )
        XCTAssertEqual(moliseEV.thisYearEUR, moliseEVThisYear.amount, accuracy: 1e-9)
        if case .evQuarterRate(let rate, _, _) = moliseEV.path {
            XCTAssertEqual(rate, 2.76, accuracy: 1e-9)
            XCTAssertEqual(moliseEV.thisYearEUR, 2.76 * 100 * 0.25, accuracy: 0.02)
        } else {
            XCTFail("Expected evQuarterRate for Molise EV post-exemption, got \(moliseEV.path)")
        }

        // Lazio EV same path shape with Lazio rate.
        let lazioEV = HowWeCalculateExplainer.bolloDetail(
            vehicle: ev,
            bookletKw: 100,
            region: .lazio,
            referenceYear: 2026,
            ownershipYears: 5
        )
        if case .evQuarterRate(let rate, _, let national) = lazioEV.path {
            XCTAssertEqual(rate, 2.84, accuracy: 1e-9)
            XCTAssertFalse(national)
        } else {
            XCTFail("Expected evQuarterRate for Lazio EV, got \(lazioEV.path)")
        }

        // Lombardia EV → permanent exempt, amount 0.
        let lombardiaEV = HowWeCalculateExplainer.bolloDetail(
            vehicle: ev,
            bookletKw: 100,
            region: .lombardia,
            referenceYear: 2026,
            ownershipYears: 5
        )
        XCTAssertEqual(lombardiaEV.path, .evPermanentExempt)
        XCTAssertEqual(lombardiaEV.averageEUR, 0, accuracy: 1e-9)
        XCTAssertEqual(lombardiaEV.thisYearEUR, 0, accuracy: 1e-9)
        XCTAssertTrue(lombardiaEV.isKnown)
    }

    func testBolloAverage_MatchesSimulatorBreakdown_EVLazioAndThermalMolise() throws {
        let refYear = Defaults.referenceCalendarYear
        // EV 2022 + 5 anni possesso: quest’anno ancora in esenzione, media orizzonte > 0.
        let ev = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2022"))
        XCTAssertEqual(ev.year, 2022)
        XCTAssertEqual(ev.powertrain, .ev)

        var evInput = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2022",
            targetBookletPowerKwP2: 100,
            italianRegion: .lazio
        )
        let evModel = HowWeCalculateExplainer.makeModel(userInput: evInput, referenceYear: refYear)
        let evBlock = try XCTUnwrap(evModel.target)
        let simulated = try XCTUnwrap(EVSimulator.simulate(input: evInput))
        XCTAssertEqual(
            evBlock.bolloAverageEUR,
            simulated.targetYearlyBreakdown.taxes,
            accuracy: 0.02,
            "Horizon average must match simulator taxes"
        )
        XCTAssertEqual(evBlock.bolloIsKnown, simulated.targetYearlyBreakdown.taxesKnown)

        let age = max(0, refYear - ev.year)
        let exemptYears = ItalianRegion.lazio.evExemptionYears(forVehicleYear: ev.year)
        if age < exemptYears {
            XCTAssertEqual(evBlock.bolloThisYearEUR, 0, accuracy: 1e-9)
            XCTAssertGreaterThan(evBlock.bolloAverageEUR, 0, "Post-exemption years pull average above 0")
            // Esempio tipico ref 2026: media ≈ 56,80 €/anno (4/5 × 71).
            XCTAssertEqual(refYear, 2026, "setUp pins referenceCalendarYearProvider to 2026")
            XCTAssertEqual(evBlock.bolloAverageEUR, 56.8, accuracy: 0.05)
        }

        // Termica Molise: media = dettaglio (tariffa stabile sull’orizzonte).
        let thermal = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-2020"))
        var thermalInput = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2022",
            sourceBookletPowerKwP2: 100,
            targetBookletPowerKwP2: 100,
            italianRegion: .molise
        )
        let thermalModel = HowWeCalculateExplainer.makeModel(userInput: thermalInput, referenceYear: refYear)
        let thermalBlock = try XCTUnwrap(thermalModel.source)
        let thermalSim = try XCTUnwrap(EVSimulator.simulate(input: thermalInput))
        XCTAssertEqual(
            thermalBlock.bolloAverageEUR,
            thermalSim.sourceYearlyBreakdown.taxes,
            accuracy: 0.02
        )
        XCTAssertEqual(thermalBlock.bolloIsKnown, thermalSim.sourceYearlyBreakdown.taxesKnown)
        if case .thermalRegional = thermalBlock.bolloPath {
            // ok
        } else {
            XCTFail("Molise ICE should use thermalRegional path, got \(thermalBlock.bolloPath)")
        }
        _ = thermal
        _ = evInput
        _ = thermalInput
    }

    func testFormatEURPerKw_UsesCurrentLocale() {
        let formatted = HowWeCalculateExplainer.formatEURPerKw(2.58)
        let nf = NumberFormatter()
        nf.locale = .autoupdatingCurrent
        nf.numberStyle = .decimal
        nf.minimumFractionDigits = 2
        nf.maximumFractionDigits = 2
        XCTAssertEqual(formatted, nf.string(from: NSNumber(value: 2.58)))
    }

    func testMakeModel_BolloSharedUsesSameConstants() throws {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            italianRegion: .molise
        )
        let model = HowWeCalculateExplainer.makeModel(userInput: input)
        XCTAssertEqual(
            model.bolloShared.nationalEVBolloEURPerKw,
            OwnershipCostEstimates.nationalEVBolloEURPerKw,
            accuracy: 1e-9
        )
        XCTAssertEqual(model.bolloShared.petrolCO2PerL100, FuelFromCO2Constants.petrolCO2PerL100, accuracy: 1e-12)
        XCTAssertEqual(model.eurLexURL, FuelFromCO2Constants.eurLexRegulationURL)
    }
}

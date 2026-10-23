//
//  VerdictAssumptionsTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class VerdictAssumptionsTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    func testElectricityLine_WeightedHomeAndPublic() {
        var input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023",
            chargingConfiguration: ChargingConfiguration(
                hasHomeCharging: true,
                homeChargingType: .home,
                publicChargingType: .publicFast,
                homeChargingShare: 0.8,
                customHomePricePerKWh: nil,
                customPublicPricePerKWh: nil
            )
        )
        let charging = input.resolvedChargingConfiguration()
        let weighted = charging.weightedCostPerKWh()
        XCTAssertEqual(weighted, 0.31 * 0.8 + ChargingType.publicFast.baseCostPerKWh * 0.2, accuracy: 0.001)

        let snap = VerdictAssumptions.snapshot(userInput: input)
        XCTAssertEqual(snap.electricityWeightedPerKWh, weighted, accuracy: 0.001)
        XCTAssertTrue(snap.hasHomeCharging)
        let line = VerdictAssumptions.electricityLine(from: snap)
        XCTAssertTrue(line.localizedCaseInsensitiveContains("80") || line.contains("80"), line)
        XCTAssertTrue(line.localizedCaseInsensitiveContains("20") || line.contains("20"), line)
        XCTAssertTrue(
            line.localizedCaseInsensitiveContains("media") || line.localizedCaseInsensitiveContains("average"),
            line
        )
        XCTAssertEqual(snap.electricityWeightedPerKWh, 0.40, accuracy: 0.02)
        _ = input
    }

    func testElectricityLine_PublicOnlyWhenNoHome() {
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: false,
            areaType: .urban,
            fuelPrice: 1.80,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: "volkswagen-golf-2020",
            targetVehicleId: "tesla-model-3-2023"
        )
        let charging = input.resolvedChargingConfiguration()
        XCTAssertEqual(charging.weightedCostPerKWh(), charging.publicChargingType.baseCostPerKWh, accuracy: 0.001)
        let snap = VerdictAssumptions.snapshot(userInput: input)
        let line = VerdictAssumptions.electricityLine(from: snap)
        XCTAssertFalse(snap.hasHomeCharging)
        XCTAssertTrue(
            line.localizedCaseInsensitiveContains("pubblic") || line.localizedCaseInsensitiveContains("public"),
            line
        )
        XCTAssertFalse(line.contains("80"), line)
    }

    func testEffectiveConsumption_MatchesEnergyCostPerYear_HomeAndUrban() throws {
        try assertEffectiveMatchesEnergyCost(hasHomeCharging: true, area: .urban)
        try assertEffectiveMatchesEnergyCost(hasHomeCharging: false, area: .urban)
        try assertEffectiveMatchesEnergyCost(hasHomeCharging: true, area: .mixed)
    }

    private func assertEffectiveMatchesEnergyCost(hasHomeCharging: Bool, area: AreaType) throws {
        let source = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-2020"))
        let target = try XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2023"))
        var input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: hasHomeCharging,
            areaType: area,
            fuelPrice: 1.85,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: source.id,
            targetVehicleId: target.id,
            scenario: .realistic,
            tripProfile: .custom
        )
        input.chargingConfiguration = ChargingConfiguration(
            hasHomeCharging: hasHomeCharging,
            publicChargingType: .publicFast,
            homeChargingShare: 0.8
        )

        let snap = VerdictAssumptions.snapshot(userInput: input)
        let simInput = OperatingCostCalculator.makeSimulationInput(from: input)
        let sim = EVSimulator()

        let sourceEnergy = sim.energyCostPerYear(
            vehicle: source,
            input: simInput,
            scenario: input.scenario,
            fuelOverrideLPerKm: nil,
            energyOverrideKWhPerKm: nil,
            asSource: true
        )
        let targetEnergy = sim.energyCostPerYear(
            vehicle: target,
            input: simInput,
            scenario: input.scenario,
            fuelOverrideLPerKm: nil,
            energyOverrideKWhPerKm: nil,
            asSource: false
        )

        let yearlyKm = Double(input.dailyKm)
        let expectedSource = yearlyKm
            * ((snap.sourceLPer100KmEffective ?? -1) / 100.0)
            * input.fuelPrice
        XCTAssertEqual(
            sourceEnergy,
            expectedSource,
            accuracy: 0.05,
            "ICE effective L/100 must rebuild energyCostPerYear (home=\(hasHomeCharging) area=\(area))"
        )

        let weighted = input.resolvedChargingConfiguration().weightedCostPerKWh()
        let expectedTarget = yearlyKm
            * ((snap.targetKWhPer100KmEffective ?? -1) / 100.0)
            * weighted
        XCTAssertEqual(
            targetEnergy,
            expectedTarget,
            accuracy: 0.05,
            "EV effective kWh/100 must rebuild energyCostPerYear (home=\(hasHomeCharging) area=\(area))"
        )

        // Urban EV multiplier < 1 → effective below raw catalog.
        if area == .urban, let catalog = target.resolvedEnergyKWhPerKm {
            XCTAssertLessThan(
                snap.targetKWhPer100KmEffective ?? 999,
                catalog * 100,
                "Urban EV effective must apply area multiplier"
            )
        }
    }

    func testAIFallback_PluralOneAndHomeVariant() {
        let oneHome = L10n.verdictAIFallbackYes(km: 12_000, min: 100, max: 200, charges: 1, hasHomeCharging: true)
        let onePublic = L10n.verdictAIFallbackYes(km: 12_000, min: 100, max: 200, charges: 1, hasHomeCharging: false)
        let many = L10n.verdictAIFallbackYes(km: 12_000, min: 100, max: 200, charges: 3, hasHomeCharging: true)
        XCTAssertFalse(oneHome.contains("1 ricariche"), oneHome)
        XCTAssertFalse(oneHome.lowercased().contains("1 charges"), oneHome)
        XCTAssertTrue(
            oneHome.localizedCaseInsensitiveContains("casa") || oneHome.localizedCaseInsensitiveContains("home"),
            oneHome
        )
        XCTAssertTrue(
            onePublic.localizedCaseInsensitiveContains("senza")
                || onePublic.localizedCaseInsensitiveContains("without")
                || onePublic.localizedCaseInsensitiveContains("pubblic")
                || onePublic.localizedCaseInsensitiveContains("public"),
            onePublic
        )
        XCTAssertFalse(many.contains("1 ricarica ") && many.contains("3 "), many)

        let notYetOne = L10n.verdictAIFallbackNotYet(10_000, 1)
        XCTAssertFalse(notYetOne.contains("1 ricariche"), notYetOne)
        XCTAssertFalse(notYetOne.lowercased().contains("1 charges"), notYetOne)
    }
}

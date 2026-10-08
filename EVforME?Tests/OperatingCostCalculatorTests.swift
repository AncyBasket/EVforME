//
//  OperatingCostCalculatorTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class OperatingCostCalculatorTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        Defaults.referenceCalendarYearProvider = { 2026 }
    }

    override func tearDown() {
        Defaults.referenceCalendarYearProvider = {
            Calendar.current.component(.year, from: Date())
        }
        super.tearDown()
    }

    func testPickerEuroPerKm_MatchesSimulator_ThreeItalianPairs() {
        struct Pair {
            let name: String
            let sourceId: String
            let targetId: String
            let fuelPrice: Double
            let sourcePrice: Double
            let targetPrice: Double
        }
        let pairs: [Pair] = [
            .init(name: "Ateca diesel → Model 3", sourceId: "seat-ateca-2016", targetId: "tesla-model-3-2024", fuelPrice: 1.75, sourcePrice: 14_000, targetPrice: 42_000),
            .init(name: "Panda GPL → Grande Panda EV", sourceId: "fiat-panda-gpl-2022", targetId: "fiat-grande-panda-ev-2024", fuelPrice: 0.85, sourcePrice: 8_000, targetPrice: 28_000),
            .init(name: "Yaris HEV → MG4", sourceId: "toyota-yaris-2022", targetId: "mg-mg4-2024", fuelPrice: 1.80, sourcePrice: 14_000, targetPrice: 32_000),
        ]

        for pair in pairs {
            guard let source = VehicleCatalogService.shared.vehicle(by: pair.sourceId),
                  let target = VehicleCatalogService.shared.vehicle(by: pair.targetId) else {
                XCTFail("Missing catalog ids for \(pair.name)")
                continue
            }
            let input = UserInput(
                dailyKm: 15_000,
                hasHomeCharging: true,
                areaType: .mixed,
                fuelPrice: pair.fuelPrice,
                ownershipYears: 5,
                electricityPricePerKWh: 0.28,
                sourceVehicleId: pair.sourceId,
                targetVehicleId: pair.targetId,
                scenario: .realistic,
                sourcePurchasePrice: pair.sourcePrice,
                targetPurchasePrice: pair.targetPrice,
                comparisonIntent: .alreadyOwned
            )
            guard let result = EVSimulator.simulate(input: input) else {
                XCTFail("Simulate failed for \(pair.name)")
                continue
            }
            let km = Double(input.dailyKm)
            let pickerSource = OperatingCostCalculator.operatingCostPerKm(vehicle: source, input: input, asSource: true)
            let pickerTarget = OperatingCostCalculator.operatingCostPerKm(vehicle: target, input: input, asSource: false)
            let simSource = result.sourceYearlyBreakdown.total / km
            let simTarget = result.targetYearlyBreakdown.total / km
            XCTAssertEqual(pickerSource, simSource, accuracy: 0.0001, "\(pair.name) source €/km")
            XCTAssertEqual(pickerTarget, simTarget, accuracy: 0.0001, "\(pair.name) target €/km")
        }
    }

    func testPHEV_UsesPetrolNotSourceDieselPrice() {
        guard let phev = VehicleCatalogService.shared.vehicle(by: "volkswagen-golf-gte-phev-2024")
                ?? VehicleCatalogService.shared.targetEVVehicles().first(where: { $0.powertrain == .phev }) else {
            XCTFail("No PHEV in catalog")
            return
        }
        var dieselInput = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.75,
            ownershipYears: 5,
            electricityPricePerKWh: 0.28,
            sourceVehicleId: "seat-ateca-2016",
            targetVehicleId: phev.id,
            scenario: .realistic,
            sourcePurchasePrice: 14_000,
            targetPurchasePrice: 36_000
        )
        let withDieselListed = OperatingCostCalculator.operatingCostPerYear(
            vehicle: phev,
            input: dieselInput,
            asSource: false
        )
        dieselInput.fuelPrice = 3.0 // absurd diesel — must NOT change PHEV fuel leg
        let withAbsurdDiesel = OperatingCostCalculator.operatingCostPerYear(
            vehicle: phev,
            input: dieselInput,
            asSource: false
        )
        XCTAssertEqual(withDieselListed, withAbsurdDiesel, accuracy: 0.01,
                       "PHEV fuel leg must use petrol, not source diesel price")
    }

    func testEdge_ZeroKm_IsFinite() {
        guard let source = VehicleCatalogService.shared.vehicle(by: "fiat-panda-2018"),
              let target = VehicleCatalogService.shared.vehicle(by: "fiat-500e-2023") else {
            XCTFail("Missing fixtures")
            return
        }
        let input = UserInput(
            dailyKm: 0,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: 0.25,
            sourceVehicleId: source.id,
            targetVehicleId: target.id,
            sourcePurchasePrice: 6_000,
            targetPurchasePrice: 28_000
        )
        let sourceYear = OperatingCostCalculator.operatingCostPerYear(vehicle: source, input: input, asSource: true)
        let targetYear = OperatingCostCalculator.operatingCostPerYear(vehicle: target, input: input, asSource: false)
        let sourcePerKm = OperatingCostCalculator.operatingCostPerKm(vehicle: source, input: input, asSource: true)
        XCTAssertTrue(sourceYear.isFinite && sourceYear >= 0)
        XCTAssertTrue(targetYear.isFinite && targetYear >= 0)
        XCTAssertTrue(sourcePerKm.isFinite && sourcePerKm >= 0)
        // Energy should be ~0 at 0 km; fixed costs (RC/tagliandi/bollo) remain.
        XCTAssertGreaterThan(sourceYear, 0)
    }

    func testEdge_HugeKm_IsFinite() {
        guard let source = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016"),
              let target = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2024") else {
            XCTFail("Missing fixtures")
            return
        }
        let input = UserInput(
            dailyKm: 200_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.8,
            ownershipYears: 5,
            electricityPricePerKWh: 0.30,
            sourceVehicleId: source.id,
            targetVehicleId: target.id,
            sourcePurchasePrice: 14_000,
            targetPurchasePrice: 40_000
        )
        let year = OperatingCostCalculator.operatingCostPerYear(vehicle: source, input: input, asSource: true)
        XCTAssertTrue(year.isFinite)
        XCTAssertGreaterThan(year, 1_000)
    }

    func testEdge_ZeroFuelPrice_IsFinite() {
        guard let source = VehicleCatalogService.shared.vehicle(by: "fiat-panda-2018") else {
            XCTFail("Missing Panda")
            return
        }
        let input = UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 0,
            ownershipYears: 5,
            electricityPricePerKWh: 0.25,
            sourceVehicleId: source.id,
            targetVehicleId: "fiat-500e-2023",
            sourcePurchasePrice: 6_000,
            targetPurchasePrice: 28_000
        )
        let energyOnly = EVSimulator().energyCostPerYear(
            vehicle: source,
            input: OperatingCostCalculator.makeSimulationInput(from: input),
            scenario: .realistic,
            fuelOverrideLPerKm: nil,
            energyOverrideKWhPerKm: nil,
            asSource: true
        )
        XCTAssertEqual(energyOnly, 0, accuracy: 0.01)
        let total = OperatingCostCalculator.operatingCostPerYear(vehicle: source, input: input, asSource: true)
        XCTAssertTrue(total.isFinite && total > 0)
    }

    func testResolvedCharging_PreservesUserPublicType() {
        var input = UserInput(
            dailyKm: 18_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: 0.22,
            sourceVehicleId: "fiat-panda-2018",
            targetVehicleId: "fiat-500e-2023",
            chargingConfiguration: ChargingConfiguration(
                hasHomeCharging: true,
                homeChargingType: .home,
                publicChargingType: .publicUltraFast,
                homeChargingShare: 0.55,
                customHomePricePerKWh: nil,
                customPublicPricePerKWh: 0.99
            )
        )
        let resolved = input.resolvedChargingConfiguration()
        XCTAssertEqual(resolved.publicChargingType, .publicUltraFast)
        XCTAssertEqual(resolved.homeChargingShare, 0.55, accuracy: 0.001)
        XCTAssertEqual(resolved.customPublicPricePerKWh, 0.99)
        XCTAssertEqual(resolved.customHomePricePerKWh, 0.22)
    }

    func testCatalogWait_WhenAlreadyLoaded_ReturnsImmediately() async {
        XCTAssertFalse(VehicleCatalogService.shared.vehicles.isEmpty)
        let start = CFAbsoluteTimeGetCurrent()
        await VehicleCatalogService.shared.waitUntilLoaded(timeoutSeconds: 2)
        let elapsed = CFAbsoluteTimeGetCurrent() - start
        XCTAssertLessThan(elapsed, 1.0)
    }

    func testReferenceCalendarYear_IsInjectable() {
        Defaults.referenceCalendarYearProvider = { 2030 }
        XCTAssertEqual(Defaults.referenceCalendarYear, 2030)
        let agePrice = Defaults.suggestedPurchasePrice(
            for: VehicleCatalogItem(
                id: "test-ice-2020",
                brand: "Test",
                model: "Car",
                year: 2020,
                powertrain: .ice,
                lengthM: 4.0,
                widthM: 1.8,
                heightM: 1.5,
                fuelConsumptionLPerKm: 0.06,
                energyConsumptionKWhPerKm: nil,
                maintenancePerYear: 400,
                taxesPerYear: 200,
                imageURL: nil,
                fuelKind: .petrol
            )
        )
        XCTAssertGreaterThan(agePrice, 0)
    }

    func testPHEVShare_ClampedAndDependsOnHomeCharging() {
        let phev = VehicleCatalogItem(
            id: "test-phev",
            brand: "Test",
            model: "PHEV",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.3,
            widthM: 1.8,
            heightM: 1.5,
            fuelConsumptionLPerKm: 0.05,
            energyConsumptionKWhPerKm: 0.18,
            maintenancePerYear: 300,
            taxesPerYear: 150,
            imageURL: nil,
            wltpRangeKm: 60,
            wltpConsumptionKWh100km: 18,
            fuelKind: .petrol
        )
        let home = phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: 15_000)
        let publicOnly = phev.phevElectricKmShare(hasHomeCharging: false, yearlyKm: 15_000)
        XCTAssertGreaterThan(home, publicOnly)
        XCTAssertGreaterThanOrEqual(home, 0.1)
        XCTAssertLessThanOrEqual(home, 0.9)
        XCTAssertGreaterThanOrEqual(publicOnly, 0.1)
        XCTAssertLessThanOrEqual(publicOnly, 0.9)
    }
}

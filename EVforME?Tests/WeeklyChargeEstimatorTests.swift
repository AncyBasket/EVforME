import XCTest
@testable import EVforME_

final class WeeklyChargeEstimatorTests: XCTestCase {
    private func makeVehicle(
        powertrain: Powertrain,
        wltpRangeKm: Int? = nil,
        batteryKWh: Double? = nil,
        energyKWhPerKm: Double? = nil
    ) -> VehicleCatalogItem {
        VehicleCatalogItem(
            id: "test-ev",
            brand: "Test",
            model: "Range",
            year: 2024,
            powertrain: powertrain,
            lengthM: 4.5,
            widthM: 1.8,
            heightM: 1.5,
            fuelConsumptionLPerKm: powertrain == .ice ? 0.06 : nil,
            energyConsumptionKWhPerKm: energyKWhPerKm,
            maintenancePerYear: 200,
            taxesPerYear: 0,
            imageURL: nil,
            batteryKWh: batteryKWh,
            wltpRangeKm: wltpRangeKm
        )
    }

    func testWeeklyCharges_KnownRange_UsesDeclaredAutonomy() {
        let vehicle = makeVehicle(powertrain: .ev, wltpRangeKm: 400)
        let range = WeeklyChargeEstimator.declaredRangeKm(for: vehicle)
        XCTAssertEqual(range, 400)

        // 15_600 km/anno → 300 km/sett; 400 km autonomia → 1 ricarica/sett.
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 15_600,
            powertrain: .ev,
            rangeKm: range,
            areaType: .mixed,
            tripProfile: .custom
        )
        XCTAssertEqual(charges, 1)
    }

    func testWeeklyCharges_MissingRange_ReturnsNil() {
        let vehicle = makeVehicle(powertrain: .ev, wltpRangeKm: nil, batteryKWh: nil, energyKWhPerKm: nil)
        XCTAssertNil(WeeklyChargeEstimator.declaredRangeKm(for: vehicle))

        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 15_000,
            powertrain: .ev,
            rangeKm: nil,
            areaType: .mixed,
            tripProfile: .custom
        )
        XCTAssertNil(charges)
    }

    func testWeeklyCharges_ZeroWeeklyKm_ReturnsZero() {
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 0,
            powertrain: .ev,
            rangeKm: 350,
            areaType: .mixed,
            tripProfile: .custom
        )
        XCTAssertEqual(charges, 0)
    }

    func testDeclaredRange_DerivedFromBatteryAndConsumption() {
        let vehicle = makeVehicle(
            powertrain: .ev,
            wltpRangeKm: nil,
            batteryKWh: 60,
            energyKWhPerKm: 0.15 // 60/0.15 = 400 km
        )
        XCTAssertEqual(WeeklyChargeEstimator.declaredRangeKm(for: vehicle), 400)
    }

    func testWeeklyCharges_Ice_ReturnsZero() {
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 15_000,
            powertrain: .ice,
            rangeKm: nil,
            areaType: .mixed,
            tripProfile: .custom
        )
        XCTAssertEqual(charges, 0)
    }
}

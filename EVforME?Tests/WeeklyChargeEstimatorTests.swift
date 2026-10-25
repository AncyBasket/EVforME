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
            fuelConsumptionLPerKm: (powertrain == .ice || powertrain == .phev) ? 0.06 : nil,
            energyConsumptionKWhPerKm: energyKWhPerKm ?? (powertrain == .ev || powertrain == .phev ? 0.15 : nil),
            maintenancePerYear: 200,
            taxesPerYear: 0,
            imageURL: nil,
            batteryKWh: batteryKWh,
            wltpRangeKm: wltpRangeKm
        )
    }

    func testWeeklyCharges_KnownRange_UsesDeclaredAutonomyExactly() {
        let vehicle = makeVehicle(powertrain: .ev, wltpRangeKm: 400)
        let range = WeeklyChargeEstimator.declaredRangeKm(for: vehicle)
        XCTAssertEqual(range, 400)

        // 15_600 km/anno → 300 km/sett; 400 km autonomia → 1 ricarica/sett.
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 15_600,
            powertrain: .ev,
            rangeKm: range,
            electricKmShare: 1.0
        )
        XCTAssertEqual(charges, 1)
    }

    func testWeeklyCharges_SameRange_IgnoresAreaAndTripProfile() {
        // I fattori zona/profilo non entrano più nel calcolo: stesso risultato ovunque.
        let urban = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 20_800,
            powertrain: .ev,
            rangeKm: 400,
            electricKmShare: 1.0
        )
        let mixed = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 20_800,
            powertrain: .ev,
            rangeKm: 400,
            electricKmShare: 1.0
        )
        // 20_800/52 = 400 km/sett → 1 ricarica con autonomia 400
        XCTAssertEqual(urban, 1)
        XCTAssertEqual(mixed, urban)
        // AreaType / TripProfile esistono ancora per i costi, ma non cambiano le ricariche.
        XCTAssertNotEqual(AreaType.urban.evConsumptionMultiplier, AreaType.mixed.evConsumptionMultiplier)
        XCTAssertNotEqual(TripProfile.commuter.evExtraMultiplier, TripProfile.weekendHighway.evExtraMultiplier)
    }

    func testWeeklyCharges_MissingRange_ReturnsNil() {
        let bare = VehicleCatalogItem(
            id: "bare",
            brand: "T",
            model: "M",
            year: 2024,
            powertrain: .ev,
            lengthM: 4,
            widthM: 1.8,
            heightM: 1.5,
            fuelConsumptionLPerKm: nil,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 0,
            taxesPerYear: 0,
            imageURL: nil
        )
        XCTAssertNil(WeeklyChargeEstimator.declaredRangeKm(for: bare))

        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 15_000,
            powertrain: .ev,
            rangeKm: nil,
            electricKmShare: 1.0
        )
        XCTAssertNil(charges)
    }

    func testWeeklyCharges_ZeroWeeklyKm_ReturnsZero() {
        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: 0,
            powertrain: .ev,
            rangeKm: 350,
            electricKmShare: 1.0
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
            electricKmShare: 0
        )
        XCTAssertEqual(charges, 0)
    }

    func testWeeklyCharges_PHEV_UsesSameElectricShareAsCostModel() {
        let phev = makeVehicle(powertrain: .phev, wltpRangeKm: 50, energyKWhPerKm: 0.18)
        let yearlyKm = 15_000.0
        let share = phev.phevElectricKmShare(hasHomeCharging: true, yearlyKm: yearlyKm)
        XCTAssertGreaterThan(share, 0)
        XCTAssertLessThanOrEqual(share, 0.6)

        let charges = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: yearlyKm,
            powertrain: .phev,
            rangeKm: 50,
            electricKmShare: share
        )
        // electric weekly = (15000/52)*share; kmPerCharge = 50
        let expected = max(1, Int(ceil((yearlyKm / 52.0) * share / 50.0)))
        XCTAssertEqual(charges, expected)

        // Share home vs no-home can differ; charges must follow the same share as cost path.
        let sharePublic = phev.phevElectricKmShare(hasHomeCharging: false, yearlyKm: yearlyKm)
        let chargesPublic = WeeklyChargeEstimator.weeklyCharges(
            yearlyKm: yearlyKm,
            powertrain: .phev,
            rangeKm: 50,
            electricKmShare: sharePublic
        )
        let expectedPublic = max(1, Int(ceil((yearlyKm / 52.0) * sharePublic / 50.0)))
        XCTAssertEqual(chargesPublic, expectedPublic)
    }

    func testChargingFearCopy_OneOrTwo_UsesFewTimes() {
        XCTAssertEqual(ChargingFearCopy.reality(for: 1), L10n.realityChargingFewTimes)
        XCTAssertEqual(ChargingFearCopy.reality(for: 2), L10n.realityChargingFewTimes)
    }

    func testChargingFearCopy_Five_UsesAboutN() {
        let reality = ChargingFearCopy.reality(for: 5)
        XCTAssertEqual(reality, L10n.realityChargingAboutTimes(5))
        XCTAssertFalse(reality == L10n.realityChargingFewTimes)
    }

    func testChargingFearCopy_Unavailable_Nil() {
        XCTAssertNil(ChargingFearCopy.reality(for: nil))
        XCTAssertNil(ChargingFearCopy.reality(for: 0))
    }
}

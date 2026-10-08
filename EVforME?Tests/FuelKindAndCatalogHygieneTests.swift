//
//  FuelKindAndCatalogHygieneTests.swift
//  EVforME?Tests
//

import XCTest
@testable import EVforME_

final class FuelKindAndCatalogHygieneTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    func testAteca2016_IsDieselForITHeuristic() {
        let ateca = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016")
        XCTAssertNotNil(ateca)
        XCTAssertEqual(ateca?.fuelKind, .diesel)
        XCTAssertEqual(ateca?.resolvedFuelKind, .diesel)
        XCTAssertEqual(ateca?.catalogFuelLabel, L10n.powertrainDieselLabel)
        // Uso reale ~7–8 L/100 (non WLTP ottimistico ~6.3).
        let l100 = (ateca?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(l100, 7.0)
        XCTAssertLessThanOrEqual(l100, 9.0)
    }

    func testPanda_IsPetrol() {
        let panda = VehicleCatalogService.shared.vehicle(by: "fiat-panda-2018")
            ?? VehicleCatalogService.shared.sourceVehicles().first { $0.model == "Panda" }
        XCTAssertNotNil(panda)
        XCTAssertEqual(panda?.resolvedFuelKind, .petrol)
    }

    func testOfficialCosts_DieselPricePreferred() {
        let costs = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.80,
            dieselPricePerLiter: 1.65,
            electricityPricePerKWh: 0.30,
            updatedAt: nil
        )
        XCTAssertEqual(costs.pricePerLiter(for: .diesel), 1.65, accuracy: 0.0001)
        XCTAssertEqual(costs.pricePerLiter(for: .petrol), 1.80, accuracy: 0.0001)
    }

    func testRecalculatePath_UsesDieselForAtecaNotPetrol() {
        // Mirror EVforMEApp.recalculateLastComparison fuel selection.
        let costs = OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: 1.80,
            dieselPricePerLiter: 1.65,
            electricityPricePerKWh: 0.30,
            updatedAt: nil
        )
        let kind = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016")?.resolvedFuelKind ?? .petrol
        XCTAssertEqual(kind, .diesel)
        XCTAssertEqual(costs.pricePerLiter(for: kind), 1.65, accuracy: 0.0001)
        XCTAssertNotEqual(costs.pricePerLiter(for: kind), costs.fuelPricePerLiter, accuracy: 0.0001)
    }

    func testCatalog_NoImpossibleAtecaPre2016() {
        let years = VehicleCatalogService.shared.vehicles
            .filter { $0.brand == "SEAT" && $0.model == "Ateca" }
            .map(\.year)
        XCTAssertFalse(years.contains { $0 < 2016 })
        XCTAssertTrue(years.contains(2016))
    }

    func testCatalog_NoJunkRadiatorNames() {
        let junk = VehicleCatalogService.shared.vehicles.filter(\.isJunkCatalogEntry)
        XCTAssertTrue(junk.isEmpty, "Junk entries should be filtered on load")
    }

    func testOperatingValueBasis_ListPriceOnOldCar_IsHaircut() {
        let basis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: 40_000,
            vehicleYear: 2016,
            electrified: false,
            referenceYear: 2026
        )
        XCTAssertLessThan(basis, 40_000)
    }

    func testOperatingValueBasis_AlreadyUsedEstimate_NotDoubleDepreciated() {
        // Stessa curva di Defaults.suggestedPurchasePrice per ICE 2016 → ~7_500.
        let suggestedUsed = 7_500.0
        let basis = OwnershipCostEstimates.operatingValueBasis(
            purchaseOrListPrice: suggestedUsed,
            vehicleYear: 2016,
            electrified: false,
            referenceYear: 2026
        )
        XCTAssertEqual(basis, suggestedUsed, accuracy: 0.01)
    }

    func testModel3_EnergyInEfficientBand() {
        let m3 = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2023")
            ?? VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2024")
        XCTAssertNotNil(m3)
        let k100 = (m3?.resolvedEnergyKWhPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(k100, 12)
        XCTAssertLessThanOrEqual(k100, 22)
    }

    func testQ4Etron_EnergyInSUVBand() {
        let q4 = VehicleCatalogService.shared.vehicle(by: "audi-q4-e-tron-2021")
        XCTAssertNotNil(q4)
        let k100 = (q4?.resolvedEnergyKWhPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(k100, 14)
        XCTAssertLessThanOrEqual(k100, 24)
    }

    func testCatalog_NoAbsurdEVEnergyOutliers() {
        let evs = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .ev }
        XCTAssertFalse(evs.isEmpty)
        for ev in evs {
            guard let kWh = ev.resolvedEnergyKWhPerKm else {
                XCTFail("EV \(ev.id) missing energy")
                continue
            }
            let k100 = kWh * 100
            XCTAssertGreaterThanOrEqual(k100, 12, "\(ev.id) too low (\(k100))")
            XCTAssertLessThanOrEqual(k100, 30, "\(ev.id) too high (\(k100))")
        }
    }

    func testCatalog_NoMissingICEFuelOrEVEnergy() {
        for v in VehicleCatalogService.shared.vehicles {
            switch v.powertrain {
            case .ice, .hev:
                XCTAssertNotNil(v.fuelConsumptionLPerKm, v.id)
                XCTAssertGreaterThan(v.fuelConsumptionLPerKm ?? 0, 0, v.id)
            case .ev:
                XCTAssertNotNil(v.resolvedEnergyKWhPerKm, v.id)
                XCTAssertGreaterThan(v.resolvedEnergyKWhPerKm ?? 0, 0, v.id)
            case .phev:
                XCTAssertNotNil(v.fuelConsumptionLPerKm, v.id)
                XCTAssertNotNil(v.resolvedEnergyKWhPerKm, v.id)
            }
        }
    }

    func testCatalog_HasHEVEntries() {
        let hevs = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .hev }
        XCTAssertFalse(hevs.isEmpty, "HEV powertrain must be present")
    }

    func testYaris2020Plus_IsHEVWithRealisticConsumption() {
        let yaris = VehicleCatalogService.shared.vehicle(by: "toyota-yaris-2020")
            ?? VehicleCatalogService.shared.vehicles.first {
                $0.brand == "Toyota" && $0.model == "Yaris" && $0.year == 2020
            }
        XCTAssertNotNil(yaris)
        XCTAssertEqual(yaris?.powertrain, .hev)
        let l100 = (yaris?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(l100, 3.5)
        XCTAssertLessThanOrEqual(l100, 5.0)
    }

    func testCatalog_HasLPGAndCNGWithPrices() {
        let lpg = VehicleCatalogService.shared.vehicles.filter { $0.resolvedFuelKind == .lpg }
        let cng = VehicleCatalogService.shared.vehicles.filter { $0.resolvedFuelKind == .cng }
        XCTAssertFalse(lpg.isEmpty, "GPL vehicles required")
        XCTAssertFalse(cng.isEmpty, "Metano vehicles required")
        let costs = OfficialCostService.shared.cachedOrBundledCosts()
            ?? OfficialEnergyCosts(
                country: "IT",
                currency: "EUR",
                fuelPricePerLiter: 1.74,
                dieselPricePerLiter: 1.66,
                lpgPricePerLiter: 0.72,
                cngPricePerKg: 1.28,
                electricityPricePerKWh: 0.33,
                updatedAt: nil
            )
        XCTAssertGreaterThan(costs.pricePerLiter(for: .lpg), 0.4)
        XCTAssertLessThan(costs.pricePerLiter(for: .lpg), 1.5)
        XCTAssertGreaterThan(costs.pricePerLiter(for: .cng), 0.8)
        XCTAssertLessThan(costs.pricePerLiter(for: .cng), 2.0)
    }

    func testCatalog_NoTeslaICEOrNonEUToys() {
        let teslaICE = VehicleCatalogService.shared.vehicles.filter {
            $0.brand.localizedCaseInsensitiveContains("Tesla") && $0.powertrain == .ice
        }
        XCTAssertTrue(teslaICE.isEmpty, "Tesla must not be ICE: \(teslaICE.map(\.id))")
        let banned = VehicleCatalogService.shared.vehicles.filter {
            let m = $0.model.lowercased()
            return $0.brand.localizedCaseInsensitiveContains("Tesla")
                && (m.contains("roadster") || m.contains("semi") || m.contains("cybertruck"))
        }
        XCTAssertTrue(banned.isEmpty, "Non-EU Tesla models must be removed: \(banned.map(\.id))")
    }

    func testCatalog_ITBestsellersPresent() {
        let ids = [
            "fiat-grande-panda-ev-2024",
            "lancia-ypsilon-hybrid-2024",
            "leapmotor-t03-2024",
            "citroen-e-c3-2024",
            "dacia-spring-2024",
            "renault-5-e-tech-2024",
            "fiat-600e-2024",
            "jeep-avenger-2024",
            "byd-dolphin-surf-2025",
            "fiat-panda-gpl-2020",
        ]
        for id in ids {
            XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: id), "Missing bestseller \(id)")
        }
    }

    func testModel3_RangeNotPlaceholder350() {
        let m3 = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2023")
            ?? VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2024")
        XCTAssertNotNil(m3)
        XCTAssertNotEqual(m3?.wltpRangeKm, 350)
        XCTAssertGreaterThanOrEqual(m3?.wltpRangeKm ?? 0, 450)
        XCTAssertLessThanOrEqual(m3?.wltpRangeKm ?? 0, 580)
    }

    func testQ4Etron_RangeNotPlaceholder350() {
        let q4 = VehicleCatalogService.shared.vehicle(by: "audi-q4-e-tron-2021")
        XCTAssertNotNil(q4)
        XCTAssertNotEqual(q4?.wltpRangeKm, 350)
        XCTAssertGreaterThanOrEqual(q4?.wltpRangeKm ?? 0, 380)
        XCTAssertLessThanOrEqual(q4?.wltpRangeKm ?? 0, 520)
    }

    func testEQV_RangeMayStayNearVanBand() {
        let eqv = VehicleCatalogService.shared.vehicle(by: "mercedes-benz-eqv-2020")
            ?? VehicleCatalogService.shared.sourceVehicles().first {
                $0.brand.localizedCaseInsensitiveContains("Mercedes") && $0.model.localizedCaseInsensitiveContains("EQV")
            }
        XCTAssertNotNil(eqv)
        let range = eqv?.wltpRangeKm ?? 0
        XCTAssertGreaterThanOrEqual(range, 250)
        XCTAssertLessThanOrEqual(range, 360)
    }

    func testCatalog_PassengerEVsNotMajorityPlaceholder350() {
        let evs = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .ev }
        XCTAssertFalse(evs.isEmpty)
        let vanNeedles = ["eqv", "e-transit", "e-crafter", "e-berlingo", "e-partner", "e-vivaro", "id. buzz", "id buzz", "transporter", "vito"]
        let passenger = evs.filter { ev in
            let blob = "\(ev.brand) \(ev.model) \(ev.trim ?? "")".lowercased()
            return !vanNeedles.contains { blob.contains($0) }
        }
        XCTAssertFalse(passenger.isEmpty)
        let n350 = passenger.filter { $0.wltpRangeKm == 350 }.count
        XCTAssertEqual(n350, 0, "Passenger EVs must not keep flat placeholder wltpRangeKm=350 (got \(n350)/\(passenger.count))")
        let fraction = Double(n350) / Double(passenger.count)
        XCTAssertLessThan(fraction, 0.05)
    }
}

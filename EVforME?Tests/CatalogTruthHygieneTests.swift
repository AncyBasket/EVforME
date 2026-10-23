//
//  CatalogTruthHygieneTests.swift
//  EVforME?Tests
//
//  Guards for fix/catalog-truth: no placeholder bollo 210, no dead models,
//  bollo↔kW coherence, ±20% EEA consumption vs fixture refs.
//

import XCTest
@testable import EVforME_

final class CatalogTruthHygieneTests: XCTestCase {

    override func setUp() {
        super.setUp()
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
    }

    /// National estimate used by catalog seed scripts (2.58 / 3.87 + superbollo >185).
    private func nationalBolloEUR(powerKw: Double, vehicleYear: Int, referenceYear: Int = 2026) -> Double {
        let base = 2.58 * min(powerKw, 100) + 3.87 * max(0, powerKw - 100)
        let sb = ItalianRegion.nationalSuperbolloEUR(
            powerKw: powerKw,
            vehicleYear: vehicleYear,
            referenceYear: referenceYear
        )
        return ((base + sb) * 100).rounded() / 100
    }

    func testCatalog_NoPlaceholderBollo210() {
        let hits = VehicleCatalogService.shared.vehicles.filter {
            abs($0.taxesPerYear - 210) < 0.01
        }
        XCTAssertTrue(
            hits.isEmpty,
            "Placeholder bollo 210 must not appear: \(hits.prefix(8).map(\.id))"
        )
    }

    func testCatalog_NoDeadModelNames() {
        let banned: [(String, String)] = [
            ("audi", "100"), ("audi", "200"), ("audi", "80"), ("audi", "90"),
            ("mercedes", "600"), ("mercedes", "190"),
            ("bmw", "228"), ("bmw", "323i"),
            ("kia", "miami"), ("nissan", "axxess"),
            ("peugeot", "405"), ("hyundai", "excel"), ("hyundai", "genesis"),
            ("ford", "bradford"),
        ]
        let vehicles = VehicleCatalogService.shared.vehicles
        for (brand, model) in banned {
            let hits = vehicles.filter {
                $0.brand.lowercased().contains(brand)
                    && $0.model.lowercased() == model
            }
            XCTAssertTrue(hits.isEmpty, "Dead model \(brand) \(model): \(hits.map(\.id))")
        }
        // Selectable junk filter must also reject Audi 100 if it ever reappears in JSON.
        let audi100 = VehicleCatalogItem(
            id: "audi-100-2022",
            brand: "Audi",
            model: "100",
            year: 2022,
            powertrain: .ice,
            lengthM: 4.8,
            widthM: 1.8,
            heightM: 1.4,
            fuelConsumptionLPerKm: 0.068,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 400,
            taxesPerYear: 210,
            imageURL: nil,
            sourceName: "seed+EEA-WLTP",
            confidenceScore: 0.9,
            fuelKind: .petrol
        )
        XCTAssertTrue(audi100.isJunkCatalogEntry)
    }

    func testCatalog_GLEBolloFromVolumeDieselNotAMG() {
        let gle = VehicleCatalogService.shared.vehicle(by: "mercedes-benz-gle-2024")
        XCTAssertNotNil(gle)
        XCTAssertEqual(gle?.resolvedFuelKind, .diesel)
        XCTAssertEqual(gle?.powerKw ?? 0, 198, accuracy: 15)
        XCTAssertLessThan(gle?.taxesPerYear ?? 9_999, 1_500)
        XCTAssertGreaterThan(gle?.taxesPerYear ?? 0, 500)
    }

    func testCatalog_BolloCoherentWithPowerKwAndFuel() {
        // When both taxesPerYear and powerKw are set, they must agree with the national
        // formula. Orphan kW left over from bad seed rows should have been cleared.
        var incoherent: [String] = []
        for v in VehicleCatalogService.shared.vehicles {
            guard v.powertrain == .ice || v.powertrain == .hev || v.powertrain == .phev else { continue }
            guard let kw = v.powerKw, kw > 0, v.taxesPerYear > 0 else { continue }
            let expect = nationalBolloEUR(powerKw: kw, vehicleYear: v.year)
            if abs(v.taxesPerYear - expect) > 2.0 {
                incoherent.append(
                    "\(v.id): tax=\(v.taxesPerYear) expect=\(expect) kw=\(kw) fuel=\(v.resolvedFuelKind)"
                )
            }
        }
        XCTAssertTrue(
            incoherent.isEmpty,
            "Bollo must match national formula from powerKw (±2€). First: \(incoherent.prefix(10))"
        )
    }

    func testCatalog_HighBolloUsesVolumeVariantNotAMG() {
        let gle = VehicleCatalogService.shared.vehicle(by: "mercedes-benz-gle-2024")
        XCTAssertNotNil(gle)
        XCTAssertLessThan(gle?.taxesPerYear ?? 9_999, 2_000)
        let rrs = VehicleCatalogService.shared.vehicle(by: "land-rover-range-rover-sport-2024")
        XCTAssertNotNil(rrs)
        XCTAssertLessThan(rrs?.taxesPerYear ?? 9_999, 2_000)
    }

    func testCatalog_Pre2018NotLabeledWLTPWithoutNEDC() {
        let bad = VehicleCatalogService.shared.vehicles.filter { v in
            guard v.year < 2018, let src = v.sourceName?.lowercased() else { return false }
            return src.contains("wltp") && !src.contains("nedc")
        }
        XCTAssertTrue(bad.isEmpty, "Pre-2018 WLTP without NEDC: \(bad.prefix(8).map(\.id))")
    }

    func testCatalog_EEARefsConsumptionWithin20Percent() throws {
        let url = try XCTUnwrap(
            Bundle(for: CatalogTruthHygieneTests.self)
                .url(forResource: "catalog_truth_eea_refs", withExtension: "json"),
            "Missing Fixtures/catalog_truth_eea_refs.json"
        )
        let data = try Data(contentsOf: url)
        let refs = try JSONSerialization.jsonObject(with: data) as? [[String: Any]]
        XCTAssertNotNil(refs)
        var failures: [String] = []
        var checked = 0
        for ref in refs ?? [] {
            guard let id = ref["id"] as? String,
                  let vehicle = VehicleCatalogService.shared.vehicle(by: id) else { continue }
            if let eeaL100 = ref["eea_l100"] as? Double {
                guard let lPerKm = vehicle.fuelConsumptionLPerKm, lPerKm > 0 else {
                    failures.append("\(id): missing fuel")
                    continue
                }
                let seed = lPerKm * 100
                let drift = abs(seed - eeaL100) / eeaL100
                checked += 1
                if drift > 0.20 {
                    failures.append(String(format: "%@: L/100 seed=%.2f eea=%.2f drift=%.0f%%", id, seed, eeaL100, drift * 100))
                }
            } else if let eeaKWh = ref["eea_kwh100"] as? Double {
                guard let k = vehicle.resolvedEnergyKWhPerKm, k > 0 else {
                    failures.append("\(id): missing energy")
                    continue
                }
                let seed = k * 100
                let drift = abs(seed - eeaKWh) / eeaKWh
                checked += 1
                if drift > 0.20 {
                    failures.append(String(format: "%@: kWh/100 seed=%.2f eea=%.2f drift=%.0f%%", id, seed, eeaKWh, drift * 100))
                }
            }
        }
        XCTAssertGreaterThan(checked, 500, "Expected hundreds of EEA refs")
        XCTAssertTrue(failures.isEmpty, "EEA ±20% failures (\(failures.count)): \(failures.prefix(12))")
    }
}

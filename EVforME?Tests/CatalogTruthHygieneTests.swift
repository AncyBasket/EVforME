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
            ("mercedes", "600"), ("mercedes", "190"), ("mercedes", "500"),
            ("bmw", "228"), ("bmw", "323i"),
            ("kia", "miami"), ("nissan", "axxess"), ("nissan", "350z"),
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
        let mb500 = VehicleCatalogItem(
            id: "mercedes-benz-500-2022",
            brand: "Mercedes-Benz",
            model: "500",
            year: 2022,
            powertrain: .ice,
            lengthM: 5.0,
            widthM: 1.9,
            heightM: 1.5,
            fuelConsumptionLPerKm: 0.12,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 800,
            taxesPerYear: 500,
            imageURL: nil,
            fuelKind: .petrol
        )
        XCTAssertTrue(mb500.isJunkCatalogEntry, "Mercedes 500 is an EEA aggregate ghost")
        let z350 = VehicleCatalogItem(
            id: "nissan-350z-2023",
            brand: "Nissan",
            model: "350Z",
            year: 2023,
            powertrain: .ice,
            lengthM: 4.3,
            widthM: 1.8,
            heightM: 1.3,
            fuelConsumptionLPerKm: 0.11,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 600,
            taxesPerYear: 400,
            imageURL: nil,
            fuelKind: .petrol
        )
        XCTAssertTrue(z350.isJunkCatalogEntry)
    }

    func testCatalog_NoEEALabelBefore2010() {
        let bad = VehicleCatalogService.shared.vehicles.filter { v in
            guard v.year < 2010, let sn = v.sourceName?.lowercased() else { return false }
            if sn.hasPrefix("stima") { return false }
            return sn.contains("seed+eea") || sn.hasPrefix("eea") || sn.contains("co2cars")
        }
        XCTAssertTrue(bad.isEmpty, "Pre-2010 must not claim EEA: \(bad.prefix(8).map(\.id))")
        // Come calcoliamo must not offer the EEA dataset link for those years.
        for v in VehicleCatalogService.shared.vehicles where v.year < 2010 {
            let cat = HowWeCalculateExplainer.consumptionSourceCategory(
                from: v.sourceName,
                vehicleYear: v.year
            )
            XCTAssertNotEqual(cat, .eeaWLTP, v.id)
            XCTAssertNotEqual(cat, .eeaNEDC, v.id)
            XCTAssertNil(HowWeCalculateExplainer.sourceURL(from: v.sourceName, category: cat), v.id)
        }
    }

    func testCatalog_Estimate2026Within20PercentOfEEA2025Sibling() {
        var failures: [String] = []
        var checked = 0
        let vehicles = VehicleCatalogService.shared.vehicles
        let byId = Dictionary(uniqueKeysWithValues: vehicles.map { ($0.id, $0) })
        for v in vehicles where v.year == 2026 {
            guard v.id.hasSuffix("-2026") else { continue }
            let sibId = String(v.id.dropLast(4)) + "2025"
            guard let sib = byId[sibId] else { continue }
            let sn = (sib.sourceName ?? "").lowercased()
            let sibIsEEA = sn.contains("eea") || sn.contains("co2cars") || sn.contains("wh/km")
            guard sibIsEEA, !sn.hasPrefix("stima") else { continue }
            checked += 1
            switch v.powertrain {
            case .ev:
                guard let a = v.resolvedEnergyKWhPerKm, let b = sib.resolvedEnergyKWhPerKm, b > 0 else {
                    failures.append("\(v.id): missing EV energy")
                    continue
                }
                if abs(a - b) / b > 0.20 {
                    failures.append(String(format: "%@: kWh/100 %.2f vs 2025 %.2f", v.id, a * 100, b * 100))
                }
            case .ice, .hev, .phev:
                guard v.resolvedFuelKind == sib.resolvedFuelKind else { continue }
                guard let a = v.fuelConsumptionLPerKm, let b = sib.fuelConsumptionLPerKm, b > 0 else {
                    failures.append("\(v.id): missing fuel")
                    continue
                }
                if abs(a - b) / b > 0.20 {
                    failures.append(String(format: "%@: L/100 %.2f vs 2025 %.2f", v.id, a * 100, b * 100))
                }
            }
        }
        XCTAssertGreaterThan(checked, 20, "Expected many 2026←2025 EEA siblings")
        XCTAssertTrue(failures.isEmpty, "2026 drift vs 2025: \(failures.prefix(12))")
    }

    func testCatalog_RestoredSeriesAndDobloPresent() {
        for id in ["bmw-1-series-2024", "bmw-3-series-2024", "bmw-5-series-2024", "fiat-doblo-2023"] {
            XCTAssertNotNil(VehicleCatalogService.shared.vehicle(by: id), id)
        }
        let one = VehicleCatalogService.shared.vehicle(by: "bmw-1-series-2024")
        XCTAssertEqual(one?.resolvedFuelKind, .diesel)
        XCTAssertLessThan(one?.taxesPerYear ?? 9_999, 800)
        XCTAssertTrue((one?.sourceName ?? "").contains("EEA"), one?.sourceName ?? "")
        let trax = VehicleCatalogService.shared.vehicle(by: "chevrolet-trax-2024")
        XCTAssertNotNil(trax)
        XCTAssertTrue((trax?.sourceName ?? "").localizedCaseInsensitiveContains("stima"))
        let g70 = VehicleCatalogService.shared.vehicle(by: "genesis-g70-2024")
        XCTAssertNotNil(g70)
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
            if src.hasPrefix("stima") { return false }
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

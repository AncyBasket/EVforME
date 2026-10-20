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
        // Audit 2026-10-19: 1.6 TDI ≈ 5,0 L/100 WLTP (non 7+ gonfiato).
        let l100 = (ateca?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertEqual(l100, 5.0, accuracy: 0.2)
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

    func testModel3_RangeNotPlaceholder350_OrNilIfUnknown() {
        let m3 = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2023")
            ?? VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2024")
        XCTAssertNotNil(m3)
        // Interpolated +N km/year ranges are cleared (nil); never keep flat 350.
        if let range = m3?.wltpRangeKm {
            XCTAssertNotEqual(range, 350)
            XCTAssertGreaterThanOrEqual(range, 450)
            XCTAssertLessThanOrEqual(range, 580)
        }
    }

    func testQ4Etron_RangeNotPlaceholder350_OrNilIfUnknown() {
        let q4 = VehicleCatalogService.shared.vehicle(by: "audi-q4-e-tron-2021")
        XCTAssertNotNil(q4)
        if let range = q4?.wltpRangeKm {
            XCTAssertNotEqual(range, 350)
            XCTAssertGreaterThanOrEqual(range, 380)
            XCTAssertLessThanOrEqual(range, 520)
        }
    }

    func testEQV_RangeMayStayNearVanBand_OrNil() {
        let eqv = VehicleCatalogService.shared.vehicle(by: "mercedes-benz-eqv-2020")
            ?? VehicleCatalogService.shared.sourceVehicles().first {
                $0.brand.localizedCaseInsensitiveContains("Mercedes") && $0.model.localizedCaseInsensitiveContains("EQV")
            }
        XCTAssertNotNil(eqv)
        if let range = eqv?.wltpRangeKm {
            XCTAssertGreaterThanOrEqual(range, 250)
            XCTAssertLessThanOrEqual(range, 360)
        }
    }

    func testCupraBorn_IsEVWithRealisticEnergy() {
        let born = VehicleCatalogService.shared.vehicle(by: "cupra-born-2023")
        XCTAssertNotNil(born)
        XCTAssertEqual(born?.powertrain, .ev)
        XCTAssertNil(born?.fuelKind)
        let k100 = (born?.resolvedEnergyKWhPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(k100, 14.5)
        XCTAssertLessThanOrEqual(k100, 17.5)
    }

    func testAriyaVariants_AllEV() {
        let ariya = VehicleCatalogService.shared.vehicles.filter {
            $0.brand.localizedCaseInsensitiveContains("Nissan") && $0.model.localizedCaseInsensitiveContains("Ariya")
        }
        XCTAssertFalse(ariya.isEmpty)
        XCTAssertTrue(ariya.allSatisfy { $0.powertrain == .ev })
        XCTAssertTrue(ariya.allSatisfy { $0.fuelKind == nil })
    }

    func testIoniq2016_22_HybridIsHEVNotPetrolICE() {
        let base = VehicleCatalogService.shared.vehicle(by: "hyundai-ioniq-2018")
        XCTAssertEqual(base?.powertrain, .hev)
        let l100 = (base?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertGreaterThanOrEqual(l100, 3.5)
        XCTAssertLessThanOrEqual(l100, 5.0)
    }

    func testCatalog_NoCorollaMatrix() {
        let matrix = VehicleCatalogService.shared.vehicles.filter {
            $0.model.localizedCaseInsensitiveContains("Matrix")
        }
        XCTAssertTrue(matrix.isEmpty)
    }

    func testCatalog_NoMonotonicConstantStepEVRanges() {
        let evs = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .ev && $0.wltpRangeKm != nil }
        let grouped = Dictionary(grouping: evs) { "\($0.brand.lowercased())|\($0.model.lowercased())" }
        for (_, rows) in grouped {
            let sorted = rows.sorted { $0.year < $1.year }
            guard sorted.count >= 3 else { continue }
            // Fail if ANY contiguous subsequence of ≥3 years has identical non-zero deltas
            // (flat stretches elsewhere in the series do not hide an interpolated ramp).
            let n = sorted.count
            for start in 0..<(n - 2) {
                for end in (start + 2)..<n {
                    let sub = Array(sorted[start...end])
                    let deltas = (0..<(sub.count - 1)).map {
                        (sub[$0 + 1].wltpRangeKm ?? 0) - (sub[$0].wltpRangeKm ?? 0)
                    }
                    let first = deltas[0]
                    if first != 0, deltas.allSatisfy({ $0 == first }) {
                        XCTFail(
                            "Interpolated +\(first) km/year subsequence \(sub.first!.year)–\(sub.last!.year) for \(sub.first!.brand) \(sub.first!.model)"
                        )
                        return
                    }
                }
            }
        }
    }

    func testCatalog_NoYearBeyondCurrentPlusOne() {
        let maxAllowed = Calendar.current.component(.year, from: Date()) + 1
        let future = VehicleCatalogService.shared.vehicles.filter { $0.year > maxAllowed }
        XCTAssertTrue(future.isEmpty, "Years > \(maxAllowed): \(future.map(\.id))")
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

    /// Audit 2026-10-19 §1: WLTP EV 11–25. Eccezioni documentate: solo furgoni / veicoli pesanti.
    func testCatalog_EVWltpConsumptionInPlausibleBand() {
        /// Furgoni e veicoli pesanti (WLTP reale spesso >25). Ogni id va giustificato.
        let documentedHeavyExceptions: Set<String> = [
            // Furgoni / LCV
            "mercedes-benz-eqv-2020", "mercedes-benz-eqv-2021", "mercedes-benz-eqv-2022",
            "mercedes-benz-eqv-2023", "mercedes-benz-eqv-2024",
            "toyota-proace-electric-2023",
            // SUV / off-road / performance pesanti (non passenger compact)
            "audi-q8-e-tron-2019", "audi-q8-e-tron-2020",
            "mercedes-benz-g-580-eq-2024",
            "porsche-taycan-2019", "porsche-taycan-2020",
        ]
        let evs = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .ev }
        XCTAssertFalse(evs.isEmpty)
        for ev in evs {
            guard let kwh100 = ev.wltpConsumptionKWh100km
                    ?? ev.energyConsumptionKWhPerKm.map({ $0 * 100 }) else {
                continue
            }
            if documentedHeavyExceptions.contains(ev.id) {
                XCTAssertGreaterThanOrEqual(kwh100, 11.0, "\(ev.id)")
                XCTAssertLessThanOrEqual(kwh100, 32.0, "\(ev.id) heavy cap")
                continue
            }
            XCTAssertGreaterThanOrEqual(kwh100, 11.0, "\(ev.id) WLTP \(kwh100) < 11")
            XCTAssertLessThanOrEqual(kwh100, 25.0, "\(ev.id) WLTP \(kwh100) > 25")
        }
    }

    func testCatalog_Model3_2026_WltpNearOfficial() {
        let m3 = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2026")
        XCTAssertNotNil(m3)
        let kwh100 = m3?.wltpConsumptionKWh100km
            ?? m3.flatMap { $0.energyConsumptionKWhPerKm.map { $0 * 100 } }
        XCTAssertNotNil(kwh100)
        XCTAssertGreaterThanOrEqual(kwh100!, 12.5)
        XCTAssertLessThanOrEqual(kwh100!, 14.5)
    }

    func testCatalog_NoSynthetic100kWhBatteryShownAsKnown() {
        let hundred = VehicleCatalogService.shared.vehicles.filter {
            $0.powertrain == .ev && ($0.batteryKWh.map { abs($0 - 100) < 0.05 } ?? false)
        }
        XCTAssertTrue(hundred.isEmpty, "Synthetic 100 kWh batteries must be null: \(hundred.map(\.id))")
    }

    /// Audit 2026-10-19 §2: Prius / Niro / CT 200h / Hybrid non devono restare `ice`.
    func testCatalog_KnownHybridsNotClassifiedAsICE() {
        let ice = VehicleCatalogService.shared.vehicles.filter { $0.powertrain == .ice }
        let offenders = ice.filter { v in
            let blob = "\(v.brand) \(v.model) \(v.trim ?? "")".lowercased()
            return blob.contains("prius")
                || blob.contains("niro")
                || blob.contains("ct 200h")
                || (blob.contains("hybrid") && !blob.contains("mild hybrid"))
        }
        XCTAssertTrue(offenders.isEmpty, "ICE hybrids: \(offenders.map(\.id))")
    }

    func testCatalog_Ateca2016_DieselNear5LPer100() {
        let ateca = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016")
        XCTAssertEqual(ateca?.resolvedFuelKind, .diesel)
        let l100 = (ateca?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertEqual(l100, 5.0, accuracy: 0.15)
    }

    /// Debito noto: media diesel EEA > benzina per questi modelli (match aggregato).
    /// Non riscrivere i consumi per far passare il test — solo allowlist o correzione con fonte.
    private static let dieselAbovePetrolKnownIssues: Set<String> = [
        "audi|a4", "audi|a6", "audi|q5", "audi|q7",
        "bmw|3 series", "bmw|5 series", "bmw|x3", "bmw|x5",
        "citroen|c5 aircross",
        "cupra|ateca", "cupra|formentor",
        "ford|kuga", "ford|mondeo",
        "hyundai|santa fe", "hyundai|tucson",
        "kia|sorento", "kia|sportage",
        "land rover|defender", "land rover|discovery", "land rover|discovery sport",
        "land rover|range rover evoque", "land rover|range rover sport",
        "mercedes-benz|c-class", "mercedes-benz|e-class", "mercedes-benz|glc", "mercedes-benz|gle",
        "mitsubishi|asx", "mitsubishi|outlander",
        "nissan|qashqai", "nissan|x-trail",
        "peugeot|3008", "peugeot|5008", "peugeot|508",
        "renault|koleos",
        "seat|ateca", "seat|tarraco",
        "skoda|karoq", "skoda|kodiaq", "skoda|octavia", "skoda|superb",
        "toyota|rav4",
        "volkswagen|passat", "volkswagen|tiguan", "volkswagen|touareg",
        "jeep|grand cherokee", "renault|kadjar",
    ]

    /// Se la media diesel di un modello supera la benzina → fallisci, salvo allowlist documentata.
    func testCatalog_DieselAverageNotAbovePetrolForSameModel() {
        let iceLike = VehicleCatalogService.shared.vehicles.filter {
            $0.powertrain == .ice || $0.powertrain == .hev
        }
        let grouped = Dictionary(grouping: iceLike) {
            "\($0.brand.lowercased())|\($0.model.lowercased())"
        }
        var unexpected: [String] = []
        for (key, rows) in grouped {
            let diesel = rows.compactMap { v -> Double? in
                guard v.resolvedFuelKind == .diesel, let l = v.fuelConsumptionLPerKm else { return nil }
                return l * 100
            }
            let petrol = rows.compactMap { v -> Double? in
                guard v.resolvedFuelKind == .petrol, let l = v.fuelConsumptionLPerKm else { return nil }
                return l * 100
            }
            guard diesel.count >= 2, petrol.count >= 2 else { continue }
            let dAvg = diesel.reduce(0, +) / Double(diesel.count)
            let pAvg = petrol.reduce(0, +) / Double(petrol.count)
            guard dAvg > pAvg + 0.05 else { continue }
            if Self.dieselAbovePetrolKnownIssues.contains(key) { continue }
            unexpected.append(
                "\(key): diesel \(String(format: "%.2f", dAvg)) > petrol \(String(format: "%.2f", pAvg))"
            )
        }
        XCTAssertTrue(
            unexpected.isEmpty,
            "Diesel avg above petrol outside known-issues allowlist:\n" + unexpected.joined(separator: "\n")
        )
        let ateca = VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016")
        let atecaL100 = (ateca?.fuelConsumptionLPerKm ?? 0) * 100
        XCTAssertEqual(atecaL100, 5.0, accuracy: 0.2)
    }

    func testCatalog_AurisHybridOnlyFrom2010_AndYarisHybridRows() {
        let auris = VehicleCatalogService.shared.vehicles.filter { $0.model.localizedCaseInsensitiveContains("auris") }
        for v in auris where v.year < 2010 {
            XCTAssertEqual(v.powertrain, .ice, v.id)
        }
        for v in auris where v.powertrain == .hev {
            XCTAssertGreaterThanOrEqual(v.year, 2010, v.id)
            XCTAssertTrue((v.trim ?? "").localizedCaseInsensitiveContains("hybrid") || v.id.contains("hybrid"), v.id)
        }
        for year in 2012...2019 {
            let hybrid = VehicleCatalogService.shared.vehicle(by: "toyota-yaris-hybrid-\(year)")
            XCTAssertNotNil(hybrid, "missing yaris hybrid \(year)")
            XCTAssertEqual(hybrid?.powertrain, .hev)
        }
    }

    func testCatalog_StimaFlagOn2025YoYCopies() {
        let stima = VehicleCatalogService.shared.vehicles.filter {
            ($0.sourceName ?? "").localizedCaseInsensitiveContains("stima")
        }
        // 36 restanti dopo correzione Model Y 2025 (EV-Database 13,1, non più copia 2024).
        XCTAssertEqual(stima.count, 36, "expected 36 stima(anno precedente) flags, got \(stima.count)")
    }

    func testCatalog_ModelY2025_EVDatabaseJuniperRWD() {
        let y = VehicleCatalogService.shared.vehicle(by: "tesla-model-y-2025")
        XCTAssertNotNil(y)
        XCTAssertEqual(y?.wltpConsumptionKWh100km ?? 0, 13.1, accuracy: 0.05)
        XCTAssertFalse((y?.sourceName ?? "").localizedCaseInsensitiveContains("stima"))
        XCTAssertTrue((y?.sourceName ?? "").localizedCaseInsensitiveContains("EV-Database"))
    }

    func testCatalog_Model32020_BolloRequiresBookletP2() {
        let m3 = VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2020")
        XCTAssertNotNil(m3)
        // powerKw EEA (picco) può restare nel seed come info, ma non entra nel bollo.
        let withoutP2 = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: m3?.taxesPerYear ?? 0,
            powertrain: .ev,
            vehicleYear: 2020,
            referenceYear: 2026,
            bookletPowerKwP2: nil
        )
        XCTAssertFalse(withoutP2.isKnown)
        XCTAssertEqual(withoutP2.amount, 0, accuracy: 0.01)

        let withP2 = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: m3?.taxesPerYear ?? 0,
            powertrain: .ev,
            vehicleYear: 2020,
            referenceYear: 2026,
            bookletPowerKwP2: 100
        )
        XCTAssertTrue(withP2.isKnown)
        XCTAssertEqual(withP2.amount, 64.50, accuracy: 0.01)
    }

    /// EV ≥ 5 anni senza P.2 → totale parziale sul verdetto (source o target).
    func testSimulation_EVOverFiveYearsWithoutP2_MarksPartialTotal() {
        VehicleCatalogService.shared.reloadFromBundledSeedIgnoringUserCacheForTesting()
        let source = try! XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "seat-ateca-2016"))
        let target = try! XCTUnwrap(VehicleCatalogService.shared.vehicle(by: "tesla-model-3-2020"))
        XCTAssertGreaterThanOrEqual(2026 - target.year, 5)
        let input = UserInput(
            dailyKm: 15_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 2.03,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: source.id,
            targetVehicleId: target.id,
            scenario: .realistic,
            sourcePurchasePrice: Defaults.suggestedPurchasePrice(for: source),
            targetPurchasePrice: Defaults.suggestedPurchasePrice(for: target),
            comparisonIntent: .alreadyOwned,
            targetBookletPowerKwP2: nil
        )
        let result = try! XCTUnwrap(EVSimulator.simulate(input: input))
        XCTAssertTrue(result.targetYearlyBreakdown.taxesKnown == false)
        XCTAssertTrue(result.hasPartialBolloTotal)
        XCTAssertTrue(result.sourceYearlyBreakdown.taxesKnown)
    }

    func testCatalog_DieselPresentForKeyITModels() {
        let catalog = VehicleCatalogService.shared.vehicles
        func hasDiesel(_ brand: String, _ model: String) -> Bool {
            catalog.contains {
                $0.brand.caseInsensitiveCompare(brand) == .orderedSame
                    && $0.model.caseInsensitiveCompare(model) == .orderedSame
                    && $0.fuelKind == .diesel
            }
        }
        XCTAssertTrue(hasDiesel("Volkswagen", "Golf"))
        XCTAssertTrue(hasDiesel("Volkswagen", "T-Roc"))
        XCTAssertTrue(hasDiesel("Fiat", "500X"))
        XCTAssertTrue(hasDiesel("Fiat", "Tipo"))
        XCTAssertTrue(hasDiesel("Mercedes-Benz", "A-Class"))
    }

    func testCatalog_LPGAndCNGPresentForKeyITModels() {
        let catalog = VehicleCatalogService.shared.vehicles
        XCTAssertTrue(catalog.contains { $0.model == "Duster" && $0.fuelKind == .lpg })
        XCTAssertTrue(catalog.contains { $0.model.localizedCaseInsensitiveContains("Sandero") && $0.fuelKind == .lpg })
        XCTAssertTrue(catalog.contains { $0.model == "i10" && $0.fuelKind == .lpg })
        XCTAssertTrue(catalog.contains { $0.model == "Panda" && $0.fuelKind == .cng })
    }

    func testCatalog_NoPHEVFlat90_NoThinPHEVFuel_EEASourceNAtLeast100() {
        let catalog = VehicleCatalogService.shared.vehicles
        let phev90 = catalog.filter { $0.powertrain == .phev && abs($0.taxesPerYear - 90) < 0.01 }
        XCTAssertTrue(phev90.isEmpty, "PHEV flat €90 removed: \(phev90.map(\.id))")

        let thinPHEV = catalog.filter { v in
            guard v.powertrain == .phev else { return false }
            let l100 = (v.fuelConsumptionLPerKm ?? 0) * 100
            let hasKWh = (v.energyConsumptionKWhPerKm ?? 0) > 0
                || (v.wltpConsumptionKWh100km ?? 0) > 0
                || (v.batteryKWh ?? 0) > 0
            return (l100 > 0 && l100 < 3.0) || !hasKWh
        }
        XCTAssertTrue(thinPHEV.isEmpty, "PHEV need CS ≥3 L/100 and kWh: \(thinPHEV.map(\.id))")

        let eeaLowN = catalog.filter { v in
            guard let sn = v.sourceName, sn.hasPrefix("EEA co2cars") else { return false }
            guard let range = sn.range(of: #"n=(\d+)"#, options: .regularExpression) else { return true }
            let digits = sn[range].dropFirst(2)
            return (Int(digits) ?? 0) < 100
        }
        XCTAssertTrue(eeaLowN.isEmpty, "EEA sourceName must have n≥100: \(eeaLowN.map(\.id))")
    }

    func testCatalog_ICEITNotOver25PercentAboveEEAManifest() throws {
        let manifestURL = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("scripts/cache/eea/fill_catalog_fuels_manifest.json")
        guard FileManager.default.fileExists(atPath: manifestURL.path) else {
            throw XCTSkip("EEA manifest not present at \(manifestURL.path)")
        }
        let data = try Data(contentsOf: manifestURL)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let corrections = json?["corrections"] as? [[String: Any]] ?? []
        var offenders: [String] = []
        for c in corrections {
            guard let id = c["id"] as? String,
                  let newL100 = c["new_l100"] as? Double,
                  let vehicle = VehicleCatalogService.shared.vehicle(by: id),
                  vehicle.powertrain == .ice,
                  let fc = vehicle.fuelConsumptionLPerKm else { continue }
            let actual = fc * 100
            if actual > newL100 * 1.25 {
                offenders.append("\(id): \(actual) > \(newL100)*1.25")
            }
        }
        XCTAssertTrue(offenders.isEmpty, offenders.joined(separator: "\n"))
    }

    func testEVBollo_RegionalRates_LinearNo387Band() {
        // Nazionale 100 kW → 64.50; 150 kW resta lineare (no +3,87 oltre 100).
        let national100 = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2018,
            referenceYear: 2026,
            bookletPowerKwP2: 100,
            italianRegion: .unspecified
        )
        XCTAssertEqual(national100.amount, 64.50, accuracy: 0.01)

        let national150 = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2018,
            referenceYear: 2026,
            bookletPowerKwP2: 150,
            italianRegion: .unspecified
        )
        XCTAssertEqual(national150.amount, 2.58 * 150 * 0.25, accuracy: 0.01)

        let lazio = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2018,
            referenceYear: 2026,
            bookletPowerKwP2: 100,
            italianRegion: .lazio
        )
        XCTAssertEqual(lazio.amount, 2.84 * 100 * 0.25, accuracy: 0.01)

        let lombardia = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2018,
            referenceYear: 2026,
            bookletPowerKwP2: 100,
            italianRegion: .lombardia
        )
        XCTAssertEqual(lombardia.amount, 0, accuracy: 0.01)
        XCTAssertTrue(lombardia.isKnown)

        let unknown = OwnershipCostEstimates.bolloPerYearDetail(
            catalogTaxesPerYear: 0,
            powertrain: .ev,
            vehicleYear: 2018,
            referenceYear: 2026,
            bookletPowerKwP2: 100,
            italianRegion: .otherUnknown
        )
        XCTAssertFalse(unknown.isKnown)
    }
}

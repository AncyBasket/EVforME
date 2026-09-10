//
//  VehicleCatalogService.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

final class VehicleCatalogService {
    static let shared = VehicleCatalogService()
    private static let minimumVehiclesForTesting = 4000

    private enum Keys {
        static let cachedCatalog = "evforme.vehicleCatalog.cached"
        static let lastUpdated = "evforme.vehicleCatalog.lastUpdated"
        static let remoteCatalogURL = "evforme.vehicleCatalog.remoteURL"
        static let cacheSeedVersion = "evforme.vehicleCatalog.cacheSeedVersion"
        static let vehicleCache = "evforme.vehicleCatalog.itemCache"
    }

    private let defaults = UserDefaults.standard
    private let seedVersion = 23
    private var remoteDisabledForTesting = false
    private let remoteSession: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 45
        config.timeoutIntervalForResource = 90
        config.waitsForConnectivity = true
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: config)
    }()

    private(set) var vehicles: [VehicleCatalogItem] = []
    private var vehicleIndexCache: [String: VehicleCatalogItem] = [:]
    private var sourceVehiclesCache: [VehicleCatalogItem]?
    private var targetEVVehiclesCache: [VehicleCatalogItem]?
    private let cacheQueue = DispatchQueue(label: "com.evforme.catalogCache", qos: .utility)
    /// Scarta load async in volo quando i test forzano il seed bundlato.
    private var loadGeneration = 0

    private init() {
        // Load catalog asynchronously to avoid blocking app startup
        loadCatalogAsync()
    }

    private func loadCatalogAsync() {
        AppLogger.shared.debug("Loading vehicle catalog asynchronously", category: .catalog)
        let generation = loadGeneration

        cacheQueue.async { [weak self] in
            guard let self = self else { return }
            let startTime = CFAbsoluteTimeGetCurrent()

            let catalog = self.expandForTestingIfNeeded(self.ensureBuiltInElectrifiedOptions(self.loadCachedOrDefault()))

            let duration = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
            AppLogger.shared.info("Catalog loaded with \(catalog.count) vehicles in \(String(format: "%.2f", duration))ms", category: .catalog)

            DispatchQueue.main.async {
                guard self.loadGeneration == generation else {
                    AppLogger.shared.debug("Skipping stale async catalog load", category: .catalog)
                    return
                }
                self.vehicles = catalog
                self.invalidateCaches()
            }
        }
    }

    private func invalidateCaches() {
        cacheQueue.sync {
            self.vehicleIndexCache.removeAll(keepingCapacity: true)
            self.sourceVehiclesCache = nil
            self.targetEVVehiclesCache = nil
        }
    }

    func sourceVehicles() -> [VehicleCatalogItem] {
        let snapshot = vehicles
        return cacheQueue.sync {
            if let cached = sourceVehiclesCache {
                return cached
            }
            let result = snapshot
                .filter { $0.powertrain.isSourceCandidate }
                .sorted { $0.displayName < $1.displayName }
            sourceVehiclesCache = result
            return result
        }
    }

    func targetEVVehicles() -> [VehicleCatalogItem] {
        let snapshot = vehicles
        return cacheQueue.sync {
            if let cached = targetEVVehiclesCache {
                return cached
            }
            let result = snapshot
                .filter { $0.powertrain.isTargetCandidate }
                .sorted { $0.displayName < $1.displayName }
            targetEVVehiclesCache = result
            return result
        }
    }

    func vehicle(by id: String) -> VehicleCatalogItem? {
        let snapshot = vehicles
        return cacheQueue.sync {
            if let cached = vehicleIndexCache[id] {
                return cached
            }
            let vehicle = snapshot.first { $0.id == id }
            if let vehicle {
                vehicleIndexCache[id] = vehicle
            }
            return vehicle
        }
    }

    /// URL remoto: override UserDefaults, altrimenti Defaults (CDN pubblico).
    var remoteCatalogURL: URL? {
        guard !remoteDisabledForTesting else { return nil }
        if let raw = defaults.string(forKey: Keys.remoteCatalogURL), !raw.isEmpty,
           let url = URL(string: raw) {
            return url
        }
        let fallback = Defaults.vehicleCatalogRemoteURL
        guard !fallback.isEmpty else { return nil }
        return URL(string: fallback)
    }

    func setRemoteCatalogURL(_ urlString: String?) {
        remoteDisabledForTesting = false
        if let urlString, !urlString.isEmpty {
            defaults.set(urlString, forKey: Keys.remoteCatalogURL)
        } else {
            defaults.removeObject(forKey: Keys.remoteCatalogURL)
        }
    }

    /// Ignora cache e URL remoto; ricarica dal seed nel bundle (catalogo stabile per unit test).
    func reloadFromBundledSeedIgnoringUserCacheForTesting() {
        loadGeneration += 1
        remoteDisabledForTesting = true
        defaults.removeObject(forKey: Keys.remoteCatalogURL)
        defaults.removeObject(forKey: Keys.cachedCatalog)
        defaults.removeObject(forKey: Keys.cacheSeedVersion)
        defaults.removeObject(forKey: Keys.lastUpdated)
        vehicles = expandForTestingIfNeeded(ensureBuiltInElectrifiedOptions(loadCachedOrDefault()))
        invalidateCaches()
    }
    
    /// Pre-warm caches for better performance
    func warmCaches() {
        // Force loading of cached lists
        _ = sourceVehicles()
        _ = targetEVVehicles()
        
        // Pre-cache frequently accessed vehicles
        let popularIds = [
            "volkswagen-golf-2026",
            "tesla-model-3-2026",
            "fiat-panda-2024",
            "renault-zoe-2024"
        ]
        
        for id in popularIds {
            _ = vehicle(by: id)
        }
    }

    func refreshFromRemoteIfPossible() async {
        // Best-effort: l’app resta usabile sul seed bundlato se la CDN fallisce.
        AppLogger.shared.debug("Starting remote catalog refresh (best-effort)", category: .catalog)

        guard let remoteCatalogURL else {
            AppLogger.shared.info("No remote catalog URL — using bundled/offline catalog", category: .catalog)
            return
        }

        do {
            var request = URLRequest(url: remoteCatalogURL)
            request.cachePolicy = .reloadIgnoringLocalCacheData
            request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")

            let startTime = CFAbsoluteTimeGetCurrent()
            let (data, response) = try await remoteSession.data(for: request)
            let duration = (CFAbsoluteTimeGetCurrent() - startTime) * 1000

            AppLogger.shared.info("Remote catalog fetch completed in \(String(format: "%.2f", duration))ms", category: .network)

            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                AppLogger.shared.warning("Catalog CDN status \(statusCode) — keeping offline catalog", category: .network)
                return
            }

            let decoded = try JSONDecoder().decode([VehicleCatalogItem].self, from: data)
            guard !decoded.isEmpty else {
                AppLogger.shared.warning("Empty remote catalog — keeping offline catalog", category: .catalog)
                return
            }

            // Non peggiorare il catalogo locale con un remote più piccolo/incompleto.
            let localCount = max(vehicles.count, loadBundledSeedCatalog()?.count ?? 0)
            if decoded.count + 50 < localCount {
                AppLogger.shared.warning(
                    "Remote catalog smaller (\(decoded.count) < \(localCount)) — keeping offline catalog",
                    category: .catalog
                )
                return
            }

            AppLogger.shared.info("Applying remote catalog (\(decoded.count) vehicles)", category: .catalog)

            await VehicleImageLoader.shared.clearAll()

            let newVehicles = expandForTestingIfNeeded(ensureBuiltInElectrifiedOptions(decoded))
            vehicles = newVehicles
            invalidateCaches()

            if let encoded = try? JSONEncoder().encode(vehicles) {
                defaults.set(encoded, forKey: Keys.cachedCatalog)
            } else {
                defaults.set(data, forKey: Keys.cachedCatalog)
            }

            defaults.set(Date().timeIntervalSince1970, forKey: Keys.lastUpdated)
            defaults.set(seedVersion, forKey: Keys.cacheSeedVersion)
            NotificationCenter.default.post(name: .evVehicleCatalogDidUpdate, object: nil)

            AppLogger.shared.info("Catalog refresh completed successfully", category: .catalog)

        } catch {
            // Offline-first: nessun alert utente per CDN down.
            AppLogger.shared.warning(
                "Catalog CDN unavailable — using bundled/offline catalog | \(error.localizedDescription)",
                category: .catalog
            )
        }
    }

    /// Aggiunge PHEV di riferimento se assenti dal seed remoto/bundle.
    private func ensureBuiltInElectrifiedOptions(_ list: [VehicleCatalogItem]) -> [VehicleCatalogItem] {
        let builtins = Self.defaultCatalog.filter { $0.powertrain == .phev }
        var out = list
        for item in builtins where !out.contains(where: { $0.id == item.id }) {
            out.append(item)
        }
        return out
    }

    private func loadCachedOrDefault() -> [VehicleCatalogItem] {
        let cachedVersion = defaults.integer(forKey: Keys.cacheSeedVersion)
        if cachedVersion == seedVersion,
           let data = defaults.data(forKey: Keys.cachedCatalog),
           let cached = try? JSONDecoder().decode([VehicleCatalogItem].self, from: data),
           !cached.isEmpty {
            return cached
        }
        if let bundled = loadBundledSeedCatalog(), !bundled.isEmpty {
            if let data = try? JSONEncoder().encode(bundled) {
                defaults.set(data, forKey: Keys.cachedCatalog)
                defaults.set(seedVersion, forKey: Keys.cacheSeedVersion)
                defaults.set(Date().timeIntervalSince1970, forKey: Keys.lastUpdated)
            }
            return bundled
        }
        return Self.defaultCatalog
    }

    private func loadBundledSeedCatalog() -> [VehicleCatalogItem]? {
        // Catalogo WLTP/EEA come sorgente primaria; fallback ai seed precedenti.
        let preferredResources: [(String, String)] = [
            ("vehicles.seed.quality", "json"),
            ("vehicles.seed.wltp_enriched", "json"),
            ("vehicles.seed.nhtsa_enriched.with_images", "json"),
            ("vehicles.seed.nhtsa_enriched", "json"),
            ("vehicles.seed", "json"),
        ]
        for (name, ext) in preferredResources {
            guard let url = Bundle.main.url(forResource: name, withExtension: ext),
                  let data = try? Data(contentsOf: url),
                  let decoded = try? JSONDecoder().decode([VehicleCatalogItem].self, from: data),
                  !decoded.isEmpty else {
                continue
            }
            return decoded
        }
        return nil
    }

    /// Per test di carico UI/ricerca genera un catalogo sintetico >= 4000 veicoli
    /// partendo dal seed reale, mantenendo coerenza base su consumi/dimensioni.
    private func expandForTestingIfNeeded(_ base: [VehicleCatalogItem]) -> [VehicleCatalogItem] {
        #if DEBUG
        guard !base.isEmpty else { return base }
        guard base.count < Self.minimumVehiclesForTesting else { return base }

        var expanded: [VehicleCatalogItem] = []
        expanded.reserveCapacity(Self.minimumVehiclesForTesting)

        let targetCount = Self.minimumVehiclesForTesting
        var variantIndex = 0
        while expanded.count < targetCount {
            for item in base {
                if expanded.count >= targetCount { break }

                let yearShift = variantIndex % 20   // distribuisce varianti su anni
                let variantYear = max(2005, item.year - 10 + yearShift)

                let fuelDelta = 1.0 + (Double((variantIndex % 11) - 5) * 0.01) // +-5%
                let energyDelta = 1.0 + (Double((variantIndex % 9) - 4) * 0.01) // +-4%
                let maintenanceDelta = 1.0 + (Double((variantIndex % 7) - 3) * 0.02) // +-6%

                let generated = VehicleCatalogItem(
                    id: "\(item.id)-v\(variantIndex)",
                    brand: item.brand,
                    model: "\(item.model) \(variantYear)",
                    year: variantYear,
                    powertrain: item.powertrain,
                    lengthM: (item.lengthM * (1.0 + Double((variantIndex % 5) - 2) * 0.002)).rounded(to: 3),
                    widthM: (item.widthM * (1.0 + Double((variantIndex % 5) - 2) * 0.0015)).rounded(to: 3),
                    heightM: (item.heightM * (1.0 + Double((variantIndex % 5) - 2) * 0.0015)).rounded(to: 3),
                    fuelConsumptionLPerKm: item.fuelConsumptionLPerKm.map { ($0 * fuelDelta).rounded(to: 4) },
                    energyConsumptionKWhPerKm: item.energyConsumptionKWhPerKm.map { ($0 * energyDelta).rounded(to: 4) },
                    maintenancePerYear: (item.maintenancePerYear * maintenanceDelta).rounded(to: 2),
                    taxesPerYear: item.taxesPerYear.rounded(to: 2),
                    imageURL: item.imageURL,
                    trim: item.trim,
                    batteryKWh: item.batteryKWh,
                    wltpRangeKm: item.wltpRangeKm,
                    wltpConsumptionKWh100km: item.wltpConsumptionKWh100km,
                    co2gKm: item.co2gKm,
                    market: item.market,
                    sourceName: item.sourceName,
                    sourceUpdatedAt: item.sourceUpdatedAt,
                    confidenceScore: item.confidenceScore
                )
                expanded.append(generated)
            }
            variantIndex += 1
        }
        return expanded
        #else
        return base
        #endif
    }

    private static let defaultCatalog: [VehicleCatalogItem] = [
        VehicleCatalogItem(
            id: "fiat-panda-2024",
            brand: "Fiat",
            model: "Panda",
            year: 2024,
            powertrain: .ice,
            lengthM: 3.69,
            widthM: 1.67,
            heightM: 1.55,
            fuelConsumptionLPerKm: 0.052,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 500,
            taxesPerYear: 150,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "vw-golf-2024",
            brand: "Volkswagen",
            model: "Golf",
            year: 2024,
            powertrain: .ice,
            lengthM: 4.28,
            widthM: 1.79,
            heightM: 1.49,
            fuelConsumptionLPerKm: 0.061,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 620,
            taxesPerYear: 210,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "toyota-rav4-2024",
            brand: "Toyota",
            model: "RAV4",
            year: 2024,
            powertrain: .ice,
            lengthM: 4.60,
            widthM: 1.86,
            heightM: 1.69,
            fuelConsumptionLPerKm: 0.074,
            energyConsumptionKWhPerKm: nil,
            maintenancePerYear: 760,
            taxesPerYear: 270,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "renault-zoe-2024",
            brand: "Renault",
            model: "Zoe",
            year: 2024,
            powertrain: .ev,
            lengthM: 4.09,
            widthM: 1.79,
            heightM: 1.56,
            fuelConsumptionLPerKm: nil,
            energyConsumptionKWhPerKm: 0.152,
            maintenancePerYear: 250,
            taxesPerYear: 0,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "tesla-model3-2024",
            brand: "Tesla",
            model: "Model 3",
            year: 2024,
            powertrain: .ev,
            lengthM: 4.72,
            widthM: 1.93,
            heightM: 1.44,
            fuelConsumptionLPerKm: nil,
            energyConsumptionKWhPerKm: 0.149,
            maintenancePerYear: 320,
            taxesPerYear: 0,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "hyundai-kona-ev-2024",
            brand: "Hyundai",
            model: "Kona EV",
            year: 2024,
            powertrain: .ev,
            lengthM: 4.36,
            widthM: 1.83,
            heightM: 1.58,
            fuelConsumptionLPerKm: nil,
            energyConsumptionKWhPerKm: 0.171,
            maintenancePerYear: 310,
            taxesPerYear: 0,
            imageURL: nil
        ),
        VehicleCatalogItem(
            id: "toyota-prius-phev-2024",
            brand: "Toyota",
            model: "Prius Plug-in",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.60,
            widthM: 1.78,
            heightM: 1.42,
            fuelConsumptionLPerKm: 0.012,
            energyConsumptionKWhPerKm: 0.145,
            maintenancePerYear: 420,
            taxesPerYear: 80,
            imageURL: nil,
            trim: "Plug-in",
            batteryKWh: 13.6,
            wltpRangeKm: 69,
            wltpConsumptionKWh100km: 14.5,
            co2gKm: 19,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        ),
        VehicleCatalogItem(
            id: "toyota-rav4-phev-2024",
            brand: "Toyota",
            model: "RAV4 Plug-in",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.60,
            widthM: 1.86,
            heightM: 1.69,
            fuelConsumptionLPerKm: 0.014,
            energyConsumptionKWhPerKm: 0.158,
            maintenancePerYear: 460,
            taxesPerYear: 90,
            imageURL: nil,
            trim: "Plug-in",
            batteryKWh: 18.1,
            wltpRangeKm: 75,
            wltpConsumptionKWh100km: 15.8,
            co2gKm: 22,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        ),
        VehicleCatalogItem(
            id: "cupra-formentor-phev-2024",
            brand: "Cupra",
            model: "Formentor e-Hybrid",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.45,
            widthM: 1.84,
            heightM: 1.51,
            fuelConsumptionLPerKm: 0.018,
            energyConsumptionKWhPerKm: 0.155,
            maintenancePerYear: 480,
            taxesPerYear: 90,
            imageURL: nil,
            trim: "e-Hybrid",
            batteryKWh: 12.8,
            wltpRangeKm: 55,
            wltpConsumptionKWh100km: 15.5,
            co2gKm: 31,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        ),
        VehicleCatalogItem(
            id: "jeep-compass-4xe-2024",
            brand: "Jeep",
            model: "Compass 4xe",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.40,
            widthM: 1.82,
            heightM: 1.65,
            fuelConsumptionLPerKm: 0.019,
            energyConsumptionKWhPerKm: 0.158,
            maintenancePerYear: 500,
            taxesPerYear: 95,
            imageURL: nil,
            trim: "4xe",
            batteryKWh: 11.4,
            wltpRangeKm: 50,
            wltpConsumptionKWh100km: 15.8,
            co2gKm: 44,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        ),
        VehicleCatalogItem(
            id: "alfa-romeo-tonale-phev-2024",
            brand: "Alfa Romeo",
            model: "Tonale PHEV",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.53,
            widthM: 1.84,
            heightM: 1.60,
            fuelConsumptionLPerKm: 0.016,
            energyConsumptionKWhPerKm: 0.152,
            maintenancePerYear: 520,
            taxesPerYear: 100,
            imageURL: nil,
            trim: "Q4",
            batteryKWh: 15.5,
            wltpRangeKm: 60,
            wltpConsumptionKWh100km: 15.2,
            co2gKm: 26,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        ),
        VehicleCatalogItem(
            id: "ford-kuga-phev-2024",
            brand: "Ford",
            model: "Kuga PHEV",
            year: 2024,
            powertrain: .phev,
            lengthM: 4.61,
            widthM: 1.88,
            heightM: 1.68,
            fuelConsumptionLPerKm: 0.015,
            energyConsumptionKWhPerKm: 0.151,
            maintenancePerYear: 470,
            taxesPerYear: 90,
            imageURL: nil,
            trim: "PHEV",
            batteryKWh: 14.4,
            wltpRangeKm: 64,
            wltpConsumptionKWh100km: 15.1,
            co2gKm: 23,
            market: "IT",
            sourceName: "manual-IT-PHEV",
            sourceUpdatedAt: nil,
            confidenceScore: 0.9
        )
    ]
}

private extension Double {
    func rounded(to decimals: Int) -> Double {
        let factor = pow(10.0, Double(decimals))
        return (self * factor).rounded() / factor
    }
}

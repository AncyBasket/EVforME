//
//  OfficialCostService.swift
//  EVforME?
//
//  Prezzi energia aggiornati all’apertura app da fonti pubbliche IT/EU.
//  Fallback: ultima cache → JSON in bundle.
//

import Foundation

final class OfficialCostService {
    static let shared = OfficialCostService()

    private enum Keys {
        static let cachedCosts = "evforme.officialCosts.cached.v1"
        static let lastFetchAt = "evforme.officialCosts.lastFetchAt"
    }

    private let defaults = UserDefaults.standard
    private let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 25
        config.timeoutIntervalForResource = 45
        config.waitsForConnectivity = true
        return URLSession(configuration: config)
    }()

    private init() {}

    /// Sempre: override API (opz.) → fonti pubbliche → cache → bundle.
    func fetchLatest() async -> OfficialEnergyCosts? {
        if let api = await fetchLegacyAPIOverride() {
            persistCache(api)
            return api
        }
        if let live = await fetchFromPublicSources() {
            persistCache(live)
            return live
        }
        if let cached = loadCache() {
            return cached
        }
        return loadBundled()
    }

    var lastSuccessfulFetchDate: Date? {
        guard let t = defaults.object(forKey: Keys.lastFetchAt) as? TimeInterval else { return nil }
        return Date(timeIntervalSince1970: t)
    }

    private func fetchLegacyAPIOverride() async -> OfficialEnergyCosts? {
        guard !Defaults.officialEnergyCostsRemoteURL.isEmpty,
              let url = URL(string: Defaults.officialEnergyCostsRemoteURL) else {
            return nil
        }
        do {
            let (data, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                ErrorHandler.shared.handleAppError(
                    .serverError(statusCode),
                    context: .network
                )
                return nil
            }
            return try JSONDecoder().decode(OfficialEnergyCosts.self, from: data)
        } catch let urlError as URLError {
            ErrorHandler.shared.handleAppError(
                urlError.toAppError,
                context: .network
            )
            return nil
        } catch {
            ErrorHandler.shared.handle(
                error,
                context: .network
            )
            return nil
        }
    }

    // MARK: - Public sources (stessa logica di scripts/fetch_official_energy_costs.py)

    private func fetchFromPublicSources() async -> OfficialEnergyCosts? {
        async let fuel = fetchMIMITBenzinaMedian()
        async let elec = fetchEurostatElectricityIT()
        let (fuelPrice, elecPrice) = await (fuel, elec)
        guard let fuelPrice, let elecPrice else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return OfficialEnergyCosts(
            country: "IT",
            currency: "EUR",
            fuelPricePerLiter: (fuelPrice * 1000).rounded() / 1000,
            electricityPricePerKWh: (elecPrice * 1000).rounded() / 1000,
            updatedAt: formatter.string(from: Date())
        )
    }

    /// MIMIT prezzo_alle_8.csv — mediana benzina self-service.
    private func fetchMIMITBenzinaMedian() async -> Double? {
        guard let url = URL(string: Defaults.mimitFuelPricesCSVURL) else { return nil }
        do {
            let (data, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode),
                  let text = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1)
            else {
                ErrorHandler.shared.handleAppError(
                    .fuelPriceFetchFailed,
                    context: .network
                )
                return nil
            }

            var prices: [Double] = []
            let lines = text.split(whereSeparator: \.isNewline)
            guard lines.count > 1 else { return nil }
            // Riga 0 = estrazione; riga 1 = header; dati da riga 2
            for line in lines.dropFirst(2) {
                let cols = line.split(separator: "|", omittingEmptySubsequences: false).map(Substring.init)
                guard cols.count >= 4 else { continue }
                let fuelName = cols[1].trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                guard fuelName == "benzina" else { continue }
                guard let parsed = parseMIMITRow(cols) else { continue }
                if parsed.isSelf, parsed.price >= 0.8, parsed.price <= 3.5 {
                    prices.append(parsed.price)
                }
            }
            guard !prices.isEmpty else { return nil }
            prices.sort()
            return prices[prices.count / 2]
        } catch let urlError as URLError {
            ErrorHandler.shared.handleAppError(
                urlError.toAppError,
                context: .network
            )
            return nil
        } catch {
            ErrorHandler.shared.handle(
                error,
                context: .network
            )
            return nil
        }
    }

    private func parseMIMITRow(_ cols: [Substring]) -> (price: Double, isSelf: Bool)? {
        // Colonne attese: …|descCarburante|prezzo|isSelf|…
        guard cols.count >= 4 else { return nil }
        let priceRaw = cols[2].trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
        let selfRaw = cols[3].trimmingCharacters(in: .whitespacesAndNewlines)
        guard let price = Double(priceRaw) else { return nil }
        return (price, selfRaw == "1")
    }

    /// Eurostat nrg_pc_204 — household IT, fascia 1000–2499 kWh, con tasse.
    private func fetchEurostatElectricityIT() async -> Double? {
        guard let url = URL(string: Defaults.eurostatElectricityURL) else { return nil }
        do {
            let (data, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                ErrorHandler.shared.handleAppError(
                    .serverError(statusCode),
                    context: .network
                )
                return nil
            }
            return try parseEurostatElectricity(data)
        } catch let urlError as URLError {
            ErrorHandler.shared.handleAppError(
                urlError.toAppError,
                context: .network
            )
            return nil
        } catch {
            ErrorHandler.shared.handle(
                error,
                context: .network
            )
            return nil
        }
    }

    private func parseEurostatElectricity(_ data: Data) throws -> Double? {
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let ids = root["id"] as? [String],
              let sizes = root["size"] as? [Int],
              let dimension = root["dimension"] as? [String: Any],
              let values = root["value"] as? [String: Any]
        else { return nil }

        var indexMaps: [String: [String: Int]] = [:]
        for dim in ids {
            guard let meta = dimension[dim] as? [String: Any],
                  let category = meta["category"] as? [String: Any],
                  let index = category["index"] as? [String: Int] else { return nil }
            indexMaps[dim] = index
        }

        guard let timeIndex = indexMaps["time"] else { return nil }
        let revTime = Dictionary(uniqueKeysWithValues: timeIndex.map { ($0.value, $0.key) })
        let timeOrder = revTime.keys.sorted()

        let target: [String: String] = [
            "freq": "S",
            "siec": "E7000",
            "nrg_cons": "KWH1000-2499",
            "unit": "KWH",
            "tax": "I_TAX",
            "currency": "EUR",
            "geo": "IT",
        ]

        for tPos in timeOrder.reversed() {
            var pos: [Int] = []
            var ok = true
            for dim in ids {
                if dim == "time" {
                    pos.append(tPos)
                    continue
                }
                guard let key = target[dim], let idx = indexMaps[dim]?[key] else {
                    ok = false
                    break
                }
                pos.append(idx)
            }
            guard ok else { continue }
            let flat = jsonStatFlatIndex(pos: pos, sizes: sizes)
            if let raw = values["\(flat)"] as? Double {
                return raw
            }
            if let num = values["\(flat)"] as? NSNumber {
                return num.doubleValue
            }
        }
        return nil
    }

    private func jsonStatFlatIndex(pos: [Int], sizes: [Int]) -> Int {
        var idx = 0
        var stride = 1
        for (p, s) in zip(pos.reversed(), sizes.reversed()) {
            idx += p * stride
            stride *= s
        }
        return idx
    }

    // MARK: - Cache / bundle

    private func persistCache(_ costs: OfficialEnergyCosts) {
        if let data = try? JSONEncoder().encode(costs) {
            defaults.set(data, forKey: Keys.cachedCosts)
            defaults.set(Date().timeIntervalSince1970, forKey: Keys.lastFetchAt)
        }
    }

    private func loadCache() -> OfficialEnergyCosts? {
        guard let data = defaults.data(forKey: Keys.cachedCosts) else { return nil }
        return try? JSONDecoder().decode(OfficialEnergyCosts.self, from: data)
    }

    private func loadBundled() -> OfficialEnergyCosts? {
        guard let url = Bundle.main.url(forResource: "official_energy_costs", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode(OfficialEnergyCosts.self, from: data) else {
            return OfficialEnergyCosts(
                country: "IT",
                currency: "EUR",
                fuelPricePerLiter: 1.739,
                electricityPricePerKWh: 0.333,
                updatedAt: nil
            )
        }
        return decoded
    }
}

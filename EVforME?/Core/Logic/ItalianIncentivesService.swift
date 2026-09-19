//
//  ItalianIncentivesService.swift
//  EVforME?
//
//  Aggiorna lo schedule incentivi IT a ogni cold start / foreground.
//  Ordine: remote URL (opz.) → cache → bundle → fallback hardcoded.
//

import Foundation

nonisolated final class ItalianIncentivesService: @unchecked Sendable {
    static let shared = ItalianIncentivesService()

    private enum Keys {
        static let cached = "evforme.italianIncentives.cached.v1"
        static let lastFetchAt = "evforme.italianIncentives.lastFetchAt"
    }

    private let defaults = UserDefaults.standard
    private let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 35
        config.waitsForConnectivity = true
        return URLSession(configuration: config)
    }()

    private let lock = NSLock()
    private var _schedule: ItalianIncentiveSchedule = .bundledFallback

    private init() {
        if let cached = loadCache() {
            _schedule = cached
        } else if let bundled = loadBundled() {
            _schedule = bundled
        }
    }

    var currentSchedule: ItalianIncentiveSchedule {
        lock.lock()
        defer { lock.unlock() }
        return _schedule
    }

    var lastSuccessfulFetchDate: Date? {
        guard let t = defaults.object(forKey: Keys.lastFetchAt) as? TimeInterval else { return nil }
        return Date(timeIntervalSince1970: t)
    }

    /// Best-effort: remote → cache → bundle. Sempre aggiorna `ItalianIncentives` in memoria.
    @discardableResult
    func refresh() async -> ItalianIncentiveSchedule {
        if let remote = await fetchRemote() {
            persistCache(remote)
            apply(remote)
            AppLogger.shared.info(
                "Italian incentives refreshed from remote (updatedAt=\(remote.updatedAt ?? "n/a"))",
                category: .network
            )
            return remote
        }
        if let cached = loadCache() {
            apply(cached)
            AppLogger.shared.info(
                "Italian incentives using cache (updatedAt=\(cached.updatedAt ?? "n/a"))",
                category: .network
            )
            return cached
        }
        if let bundled = loadBundled() {
            apply(bundled)
            AppLogger.shared.info(
                "Italian incentives using bundle (updatedAt=\(bundled.updatedAt ?? "n/a"))",
                category: .network
            )
            return bundled
        }
        apply(.bundledFallback)
        AppLogger.shared.warning("Italian incentives fallback hardcoded schedule", category: .network)
        return .bundledFallback
    }

    private func apply(_ schedule: ItalianIncentiveSchedule) {
        lock.lock()
        _schedule = schedule
        lock.unlock()
    }

    private func fetchRemote() async -> ItalianIncentiveSchedule? {
        guard !Defaults.italianIncentivesRemoteURL.isEmpty,
              let url = URL(string: Defaults.italianIncentivesRemoteURL) else {
            return nil
        }
        do {
            let (data, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                AppLogger.shared.warning(
                    "Italian incentives remote status \(statusCode) — keeping cache/bundle",
                    category: .network
                )
                return nil
            }
            return try JSONDecoder().decode(ItalianIncentiveSchedule.self, from: data)
        } catch {
            AppLogger.shared.warning(
                "Italian incentives remote fetch failed — keeping cache/bundle",
                category: .network
            )
            return nil
        }
    }

    private func persistCache(_ schedule: ItalianIncentiveSchedule) {
        if let data = try? JSONEncoder().encode(schedule) {
            defaults.set(data, forKey: Keys.cached)
            defaults.set(Date().timeIntervalSince1970, forKey: Keys.lastFetchAt)
        }
    }

    private func loadCache() -> ItalianIncentiveSchedule? {
        guard let data = defaults.data(forKey: Keys.cached) else { return nil }
        return try? JSONDecoder().decode(ItalianIncentiveSchedule.self, from: data)
    }

    private func loadBundled() -> ItalianIncentiveSchedule? {
        guard let url = Bundle.main.url(forResource: "italian_incentives", withExtension: "json"),
              let data = try? Data(contentsOf: url) else {
            return nil
        }
        return try? JSONDecoder().decode(ItalianIncentiveSchedule.self, from: data)
    }
}

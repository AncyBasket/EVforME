//
//  VehicleImageLoader.swift
//  EVforME?
//
//  Carica foto catalogo con User-Agent esplicito (Wikimedia rifiuta client anonimi).
//

import Foundation
import UIKit

extension Notification.Name {
    static let evVehicleCatalogDidUpdate = Notification.Name("evforme.vehicleCatalog.didUpdate")
}

actor VehicleImageLoader {
    static let shared = VehicleImageLoader()

    private var memory: [URL: UIImage] = [:]
    private let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 35
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.httpAdditionalHeaders = [
            "User-Agent": "EVforME/1.0 (iOS; vehicle catalog images; contact: local)",
            "Accept": "image/*,*/*;q=0.8",
        ]
        return URLSession(configuration: config)
    }()

    func image(for url: URL) async -> UIImage? {
        if let cached = memory[url] { return cached }
        do {
            var request = URLRequest(url: url)
            request.cachePolicy = .reloadIgnoringLocalCacheData
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode),
                  let image = UIImage(data: data) else {
                return nil
            }
            memory[url] = image
            return image
        } catch {
            return nil
        }
    }

    func clearAll() {
        memory.removeAll(keepingCapacity: true)
    }
}

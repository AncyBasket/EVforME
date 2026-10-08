//
//  MarketLocationResolver.swift
//  EVforME?
//
//  Consenso When-In-Use → una lettura GPS → reverse geocode → ISO paese.
//  Nessun tracking in background; coordinate non persistite.
//

import Combine
import CoreLocation
import Foundation

@MainActor
final class MarketLocationResolver: NSObject, ObservableObject {
    enum Status: Equatable {
        case idle
        case requestingPermission
        case locating
        case resolvingCountry
        case ready(AppMarket)
        case denied
        case failed
        case timedOut
    }

    @Published private(set) var status: Status = .idle
    @Published private(set) var authorizationStatus: CLAuthorizationStatus

    private let manager = CLLocationManager()
    private let geocoder = CLGeocoder()
    private var timeoutTask: Task<Void, Never>?

    override init() {
        authorizationStatus = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    /// Richiede permesso (se serve) e risolve il paese. Una sola lettura.
    func resolveMarketFromLocation() {
        authorizationStatus = manager.authorizationStatus
        switch manager.authorizationStatus {
        case .notDetermined:
            status = .requestingPermission
            manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            startOneShotLocation()
        case .denied, .restricted:
            status = .denied
        @unknown default:
            status = .denied
        }
    }

    private func startOneShotLocation() {
        geocoder.cancelGeocode()
        status = .locating
        timeoutTask?.cancel()
        timeoutTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 15_000_000_000)
            guard let self, !Task.isCancelled else { return }
            switch self.status {
            case .locating, .resolvingCountry, .requestingPermission:
                self.status = .timedOut
                self.manager.stopUpdatingLocation()
                self.geocoder.cancelGeocode()
            default:
                break
            }
        }
        manager.requestLocation()
    }

    private func resolveCountry(from location: CLLocation) {
        status = .resolvingCountry
        geocoder.cancelGeocode()
        geocoder.reverseGeocodeLocation(location) { [weak self] placemarks, error in
            Task { @MainActor in
                guard let self else { return }
                self.timeoutTask?.cancel()
                self.timeoutTask = nil
                if error != nil || placemarks?.isEmpty != false {
                    self.status = .failed
                    return
                }
                let iso = placemarks?.first?.isoCountryCode
                let market = AppMarket.from(isoCountryCode: iso)
                self.status = .ready(market)
            }
        }
    }
}

extension MarketLocationResolver: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            self.authorizationStatus = manager.authorizationStatus
            switch manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                if case .requestingPermission = self.status {
                    self.startOneShotLocation()
                }
            case .denied, .restricted:
                self.status = .denied
            case .notDetermined:
                break
            @unknown default:
                self.status = .denied
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        Task { @MainActor in
            self.manager.stopUpdatingLocation()
            self.resolveCountry(from: location)
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            self.timeoutTask?.cancel()
            self.timeoutTask = nil
            if case .ready = self.status { return }
            self.status = .failed
        }
    }
}

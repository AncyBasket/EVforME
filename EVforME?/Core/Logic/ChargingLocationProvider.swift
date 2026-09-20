//
//  ChargingLocationProvider.swift
//  EVforME?
//
//  Location When In Use solo on-demand (apertura mappa colonnine). Niente background.
//

import Combine
import CoreLocation
import Foundation

@MainActor
final class ChargingLocationProvider: NSObject, ObservableObject {
    enum Status: Equatable {
        case idle
        case requestingPermission
        case locating
        case ready(CLLocationCoordinate2D)
        case denied
        case failed
        case timedOut

        static func == (lhs: Status, rhs: Status) -> Bool {
            switch (lhs, rhs) {
            case (.idle, .idle),
                 (.requestingPermission, .requestingPermission),
                 (.locating, .locating),
                 (.denied, .denied),
                 (.failed, .failed),
                 (.timedOut, .timedOut):
                return true
            case (.ready(let a), .ready(let b)):
                return a.latitude == b.latitude && a.longitude == b.longitude
            default:
                return false
            }
        }
    }

    @Published private(set) var status: Status = .idle
    @Published private(set) var authorizationStatus: CLAuthorizationStatus

    private let manager = CLLocationManager()
    private var timeoutTask: Task<Void, Never>?

    override init() {
        authorizationStatus = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    var coordinate: CLLocationCoordinate2D? {
        if case .ready(let coord) = status { return coord }
        return nil
    }

    /// Chiama solo quando l’utente apre la mappa / attiva “usa posizione”.
    func requestLocationWhenInUse() {
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
        status = .locating
        timeoutTask?.cancel()
        timeoutTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 12_000_000_000)
            guard let self, !Task.isCancelled else { return }
            if case .locating = self.status {
                self.status = .timedOut
                self.manager.stopUpdatingLocation()
            }
        }
        manager.requestLocation()
    }
}

extension ChargingLocationProvider: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            self.authorizationStatus = manager.authorizationStatus
            switch manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                self.startOneShotLocation()
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
            self.timeoutTask?.cancel()
            self.timeoutTask = nil
            self.manager.stopUpdatingLocation()
            self.status = .ready(location.coordinate)
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

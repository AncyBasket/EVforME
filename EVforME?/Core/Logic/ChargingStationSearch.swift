//
//  ChargingStationSearch.swift
//  EVforME?
//
//  Helper puri per colonnine 1.3 — MKLocalSearch / Mappe Apple, zero API key.
//

import CoreLocation
import Foundation
import MapKit

struct ChargingStationPin: Identifiable, Equatable, Hashable {
    let id: String
    let name: String
    let coordinate: CLLocationCoordinate2D
    let distanceMeters: CLLocationDistance?
    let addressLine: String?

    static func == (lhs: ChargingStationPin, rhs: ChargingStationPin) -> Bool {
        lhs.id == rhs.id
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
}

enum ChargingStationSearch {
    static let defaultRadiusMeters: CLLocationDistance = 20_000
    static let maxResults = 25

    /// Query orientative per MapKit / deep link Mappe.
    static func naturalLanguageQuery(locale: Locale = .current) -> String {
        let lang = locale.language.languageCode?.identifier ?? locale.identifier
        if lang.hasPrefix("it") {
            return "ricarica elettrica"
        }
        return "EV charging"
    }

    /// Centro fallback IT quando non c’è GPS (urbano → Roma, misto → Bologna).
    static func fallbackCoordinate(for areaType: AreaType) -> CLLocationCoordinate2D {
        switch areaType {
        case .urban:
            return CLLocationCoordinate2D(latitude: 41.9028, longitude: 12.4964) // Roma
        case .mixed:
            return CLLocationCoordinate2D(latitude: 44.4949, longitude: 11.3426) // Bologna
        }
    }

    static func appleMapsSearchURL(
        query: String? = nil,
        near coordinate: CLLocationCoordinate2D? = nil,
        locale: Locale = .current
    ) -> URL {
        let q = (query?.trimmingCharacters(in: .whitespacesAndNewlines)).flatMap { $0.isEmpty ? nil : $0 }
            ?? naturalLanguageQuery(locale: locale)
        var components = URLComponents(string: "https://maps.apple.com/")!
        var items: [URLQueryItem] = [
            URLQueryItem(name: "q", value: q)
        ]
        if let coordinate {
            items.append(URLQueryItem(name: "ll", value: String(format: "%.5f,%.5f", coordinate.latitude, coordinate.longitude)))
        }
        components.queryItems = items
        return components.url!
    }

    static func directionsURL(to pin: ChargingStationPin) -> URL {
        var components = URLComponents(string: "https://maps.apple.com/")!
        components.queryItems = [
            URLQueryItem(name: "daddr", value: String(format: "%.5f,%.5f", pin.coordinate.latitude, pin.coordinate.longitude)),
            URLQueryItem(name: "dirflg", value: "d")
        ]
        return components.url!
    }

    static func formatDistanceMeters(_ meters: CLLocationDistance?) -> String? {
        guard let meters, meters.isFinite, meters >= 0 else { return nil }
        if meters < 1000 {
            return String(format: "%.0f m", meters)
        }
        return String(format: "%.1f km", meters / 1000)
    }

    static func region(around center: CLLocationCoordinate2D, radiusMeters: CLLocationDistance = defaultRadiusMeters) -> MKCoordinateRegion {
        MKCoordinateRegion(
            center: center,
            latitudinalMeters: radiusMeters * 2,
            longitudinalMeters: radiusMeters * 2
        )
    }

    /// Costruisce pin da `MKMapItem` (testabile senza rete se si passa lista vuota / mock).
    static func pins(
        from items: [MKMapItem],
        relativeTo origin: CLLocationCoordinate2D?,
        limit: Int = maxResults
    ) -> [ChargingStationPin] {
        let originLocation = origin.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) }
        var seen = Set<String>()
        var result: [ChargingStationPin] = []
        for item in items {
            let coord = item.placemark.coordinate
            guard CLLocationCoordinate2DIsValid(coord) else { continue }
            let name = item.name?.trimmingCharacters(in: .whitespacesAndNewlines)
            let title = (name?.isEmpty == false) ? name! : L10n.chargingMapUnnamedStation
            let id = "\(title)-\(String(format: "%.5f", coord.latitude))-\(String(format: "%.5f", coord.longitude))"
            guard seen.insert(id).inserted else { continue }
            let distance: CLLocationDistance? = originLocation.map {
                $0.distance(from: CLLocation(latitude: coord.latitude, longitude: coord.longitude))
            }
            let address = [
                item.placemark.thoroughfare,
                item.placemark.locality
            ]
            .compactMap { $0 }
            .joined(separator: ", ")
            result.append(
                ChargingStationPin(
                    id: id,
                    name: title,
                    coordinate: coord,
                    distanceMeters: distance,
                    addressLine: address.isEmpty ? nil : address
                )
            )
        }
        return Array(
            result
                .sorted {
                    ($0.distanceMeters ?? .greatestFiniteMagnitude) < ($1.distanceMeters ?? .greatestFiniteMagnitude)
                }
                .prefix(max(0, limit))
        )
    }

    @MainActor
    static func searchNearby(
        coordinate: CLLocationCoordinate2D,
        radiusMeters: CLLocationDistance = defaultRadiusMeters,
        locale: Locale = .current
    ) async throws -> [ChargingStationPin] {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = naturalLanguageQuery(locale: locale)
        request.resultTypes = [.pointOfInterest, .address]
        request.region = region(around: coordinate, radiusMeters: radiusMeters)
        request.pointOfInterestFilter = MKPointOfInterestFilter(including: [.evCharger])
        let search = MKLocalSearch(request: request)
        let response = try await search.start()
        let pins = pins(from: response.mapItems, relativeTo: coordinate)
        if pins.isEmpty {
            // Retry senza filtro POI stretto (alcune regioni non etichettano EV charger).
            let loose = MKLocalSearch.Request()
            loose.naturalLanguageQuery = naturalLanguageQuery(locale: locale)
            loose.region = region(around: coordinate, radiusMeters: radiusMeters)
            let looseResponse = try await MKLocalSearch(request: loose).start()
            return Self.pins(from: looseResponse.mapItems, relativeTo: coordinate)
        }
        return pins
    }

    @MainActor
    static func geocodeCity(_ city: String) async throws -> CLLocationCoordinate2D {
        let trimmed = city.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw ChargingStationSearchError.emptyCity
        }
        let geocoder = CLGeocoder()
        let marks = try await geocoder.geocodeAddressString(trimmed)
        guard let coord = marks.first?.location?.coordinate, CLLocationCoordinate2DIsValid(coord) else {
            throw ChargingStationSearchError.geocodeFailed
        }
        return coord
    }
}

enum ChargingStationSearchError: Error, Equatable {
    case emptyCity
    case geocodeFailed
}

//
//  ChargingStationSearchTests.swift
//  EVforME?Tests
//

import CoreLocation
import MapKit
import XCTest
@testable import EVforME_

final class ChargingStationSearchTests: XCTestCase {
    func testItalianLocaleQuery() {
        let locale = Locale(identifier: "it_IT")
        XCTAssertEqual(ChargingStationSearch.naturalLanguageQuery(locale: locale), "ricarica elettrica")
    }

    func testEnglishLocaleQuery() {
        let locale = Locale(identifier: "en_US")
        XCTAssertEqual(ChargingStationSearch.naturalLanguageQuery(locale: locale), "EV charging")
    }

    func testFallbackCoordinatesDifferByArea() {
        let urban = ChargingStationSearch.fallbackCoordinate(for: .urban)
        let mixed = ChargingStationSearch.fallbackCoordinate(for: .mixed)
        XCTAssertNotEqual(urban.latitude, mixed.latitude, accuracy: 0.0001)
        XCTAssertTrue(CLLocationCoordinate2DIsValid(urban))
        XCTAssertTrue(CLLocationCoordinate2DIsValid(mixed))
    }

    func testAppleMapsURLContainsQuery() {
        let url = ChargingStationSearch.appleMapsSearchURL(
            query: "ricarica elettrica",
            near: CLLocationCoordinate2D(latitude: 45.46, longitude: 9.19),
            locale: Locale(identifier: "it_IT")
        )
        let s = url.absoluteString
        XCTAssertTrue(s.contains("maps.apple.com"))
        XCTAssertTrue(s.contains("q="))
        XCTAssertTrue(s.contains("ll="))
    }

    func testFormatDistance() {
        XCTAssertEqual(ChargingStationSearch.formatDistanceMeters(450), "450 m")
        XCTAssertEqual(ChargingStationSearch.formatDistanceMeters(2_400), "2.4 km")
        XCTAssertNil(ChargingStationSearch.formatDistanceMeters(nil))
    }

    func testPinsRespectLimitAndSortByDistance() {
        let origin = CLLocationCoordinate2D(latitude: 45.0, longitude: 9.0)
        let near = makeItem(name: "Near", lat: 45.01, lon: 9.0)
        let far = makeItem(name: "Far", lat: 45.20, lon: 9.0)
        let pins = ChargingStationSearch.pins(from: [far, near], relativeTo: origin, limit: 1)
        XCTAssertEqual(pins.count, 1)
        XCTAssertEqual(pins.first?.name, "Near")
    }

    func testPinsDropResultsBeyondMaxDistance() {
        // Milano → Udine ~462 km must not appear for a city search.
        let milano = CLLocationCoordinate2D(latitude: 45.4642, longitude: 9.1900)
        let local = makeItem(name: "Milano charger", lat: 45.47, lon: 9.20)
        let udine = makeItem(name: "Udine charger", lat: 46.07, lon: 13.23)
        let pins = ChargingStationSearch.pins(
            from: [udine, local],
            relativeTo: milano,
            maxDistanceMeters: ChargingStationSearch.maxResultDistanceMeters
        )
        XCTAssertEqual(pins.map(\.name), ["Milano charger"])
        let empty = ChargingStationSearch.pins(
            from: [udine],
            relativeTo: milano,
            maxDistanceMeters: ChargingStationSearch.maxResultDistanceMeters
        )
        XCTAssertTrue(empty.isEmpty, "no pins within radius → empty (UI shows nessun risultato)")
    }

    func testRegionHasPositiveSpan() {
        let region = ChargingStationSearch.region(
            around: CLLocationCoordinate2D(latitude: 41.9, longitude: 12.5),
            radiusMeters: 10_000
        )
        XCTAssertGreaterThan(region.span.latitudeDelta, 0)
        XCTAssertGreaterThan(region.span.longitudeDelta, 0)
    }

    private func makeItem(name: String, lat: Double, lon: Double) -> MKMapItem {
        let placemark = MKPlacemark(coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon))
        let item = MKMapItem(placemark: placemark)
        item.name = name
        return item
    }
}

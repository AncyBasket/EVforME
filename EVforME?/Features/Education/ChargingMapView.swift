//
//  ChargingMapView.swift
//  EVforME?
//
//  Mappa leggera colonnine via MapKit (MKLocalSearch). Niente API a pagamento.
//

import CoreLocation
import MapKit
import SwiftUI

struct ChargingMapView: View {
    var areaType: AreaType = .mixed

    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @Environment(\.locale) private var locale

    @StateObject private var locationProvider = ChargingLocationProvider()
    @State private var useDeviceLocation = true
    @State private var cityQuery = ""
    @State private var pins: [ChargingStationPin] = []
    @State private var selectedPin: ChargingStationPin?
    @State private var cameraPosition: MapCameraPosition = .automatic
    @State private var searchCenter: CLLocationCoordinate2D?
    @State private var isSearching = false
    @State private var statusMessage: String?
    @State private var didInitialLoad = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                controls
                ZStack(alignment: .bottom) {
                    mapLayer
                    if let statusMessage, pins.isEmpty, !isSearching {
                        emptyBanner(statusMessage)
                    }
                    if isSearching
                        || locationProvider.status == .locating
                        || locationProvider.status == .requestingPermission {
                        ProgressView()
                            .padding(14)
                            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                            .padding(.bottom, 24)
                    }
                }
                disclaimerBar
            }
            .background(Color.appScreenBackground.ignoresSafeArea())
            .navigationTitle(L10n.chargingMapTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.guidesSheetClose) { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button(L10n.chargingMapOpenInMaps) {
                        openAppleMapsFallback()
                    }
                }
            }
            .task {
                guard !didInitialLoad else { return }
                didInitialLoad = true
                await bootstrap()
            }
            .onChange(of: locationProvider.status) { _, newStatus in
                Task { await handleLocationStatus(newStatus) }
            }
            .sheet(item: $selectedPin) { pin in
                pinDetailSheet(pin)
                    .presentationDetents([.medium])
            }
        }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker(L10n.chargingMapModeLabel, selection: $useDeviceLocation) {
                Text(L10n.chargingMapModeLocation).tag(true)
                Text(L10n.chargingMapModeCity).tag(false)
            }
            .pickerStyle(.segmented)
            .onChange(of: useDeviceLocation) { _, useLoc in
                Task {
                    if useLoc {
                        locationProvider.requestLocationWhenInUse()
                    } else {
                        await searchByCityIfPossible()
                    }
                }
            }

            if !useDeviceLocation {
                HStack(spacing: 8) {
                    TextField(L10n.chargingMapCityPlaceholder, text: $cityQuery)
                        .textFieldStyle(.roundedBorder)
                        .textInputAutocapitalization(.words)
                        .submitLabel(.search)
                        .onSubmit {
                            Task { await searchByCityIfPossible() }
                        }
                    Button(L10n.chargingMapSearch) {
                        Task { await searchByCityIfPossible() }
                    }
                    .font(Typography.bodyBold)
                    .foregroundStyle(Color.ink)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private var mapLayer: some View {
        Map(position: $cameraPosition, selection: $selectedPin) {
            ForEach(pins) { pin in
                Marker(pin.name, coordinate: pin.coordinate)
                    .tint(Color.accent)
                    .tag(pin)
            }
            if let searchCenter {
                Marker(L10n.chargingMapSearchCenter, coordinate: searchCenter)
                    .tint(Color.ink.opacity(0.55))
            }
        }
        .mapStyle(.standard)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var disclaimerBar: some View {
        Text(L10n.chargingMapDisclaimer)
            .font(Typography.readingCaption)
            .foregroundStyle(Color.secondaryText)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.appChrome.opacity(0.95))
    }

    private func emptyBanner(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(message)
                .font(Typography.readingCaption)
                .foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
            Button(L10n.chargingMapOpenInMaps) {
                openAppleMapsFallback()
            }
            .font(Typography.bodyBold)
            .foregroundStyle(Color.ink)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .padding(16)
    }

    private func pinDetailSheet(_ pin: ChargingStationPin) -> some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 12) {
                Text(pin.name)
                    .font(Typography.readingTitle)
                    .foregroundStyle(Color.ink)
                if let address = pin.addressLine {
                    Text(address)
                        .font(Typography.readingBody)
                        .foregroundStyle(Color.secondaryText)
                }
                if let distance = ChargingStationSearch.formatDistanceMeters(pin.distanceMeters) {
                    Text(L10n.chargingMapDistance(distance))
                        .font(Typography.readingCaption)
                        .foregroundStyle(Color.secondaryText)
                }
                PrimaryButton(title: L10n.chargingMapDirections) {
                    openURL(ChargingStationSearch.directionsURL(to: pin))
                }
                Spacer(minLength: 0)
            }
            .padding(24)
            .background(Color.appScreenBackground.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.guidesSheetClose) { selectedPin = nil }
                }
            }
        }
    }

    private func bootstrap() async {
        if useDeviceLocation {
            locationProvider.requestLocationWhenInUse()
            if case .denied = locationProvider.status {
                await runSearch(
                    at: ChargingStationSearch.fallbackCoordinate(for: areaType),
                    note: L10n.chargingMapUsingFallbackCity
                )
            }
        } else {
            await runSearch(
                at: ChargingStationSearch.fallbackCoordinate(for: areaType),
                note: L10n.chargingMapUsingFallbackCity
            )
        }
    }

    private func handleLocationStatus(_ status: ChargingLocationProvider.Status) async {
        guard useDeviceLocation else { return }
        switch status {
        case .ready(let coord):
            await runSearch(at: coord, note: nil)
        case .denied:
            await runSearch(
                at: ChargingStationSearch.fallbackCoordinate(for: areaType),
                note: L10n.chargingMapLocationDenied
            )
        case .failed, .timedOut:
            await runSearch(
                at: ChargingStationSearch.fallbackCoordinate(for: areaType),
                note: L10n.chargingMapLocationUnavailable
            )
        case .idle, .requestingPermission, .locating:
            break
        }
    }

    private func searchByCityIfPossible() async {
        let trimmed = cityQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            await runSearch(
                at: ChargingStationSearch.fallbackCoordinate(for: areaType),
                note: L10n.chargingMapUsingFallbackCity
            )
            return
        }
        isSearching = true
        statusMessage = nil
        defer { isSearching = false }
        do {
            let coord = try await ChargingStationSearch.geocodeCity(trimmed)
            await runSearch(at: coord, note: nil)
        } catch {
            pins = []
            statusMessage = L10n.chargingMapCityNotFound
        }
    }

    private func runSearch(at coordinate: CLLocationCoordinate2D, note: String?) async {
        isSearching = true
        statusMessage = note
        searchCenter = coordinate
        cameraPosition = .region(ChargingStationSearch.region(around: coordinate))
        defer { isSearching = false }
        do {
            let found = try await ChargingStationSearch.searchNearby(
                coordinate: coordinate,
                locale: locale
            )
            pins = found
            if found.isEmpty {
                statusMessage = note ?? L10n.chargingMapNoResults
            } else {
                statusMessage = nil
            }
            if let first = found.first {
                cameraPosition = .region(
                    ChargingStationSearch.region(around: first.coordinate, radiusMeters: 8_000)
                )
            }
        } catch {
            pins = []
            statusMessage = L10n.chargingMapSearchFailed
        }
    }

    private func openAppleMapsFallback() {
        let url = ChargingStationSearch.appleMapsSearchURL(
            near: searchCenter ?? locationProvider.coordinate,
            locale: locale
        )
        openURL(url)
    }
}

#Preview {
    ChargingMapView(areaType: .urban)
}

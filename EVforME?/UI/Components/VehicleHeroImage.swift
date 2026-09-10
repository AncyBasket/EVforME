//
//  VehicleHeroImage.swift
//  EVforME?
//

import SwiftUI

/// Foto veicolo. La dimensione ideale resta vincolata (niente layout “esploso”).
struct VehicleHeroImage: View {
    let vehicle: VehicleCatalogItem
    var height: CGFloat = 120
    var cornerRadius: CGFloat = 14
    var showsLabelsBelow: Bool = true
    /// Miniatura quadrata (liste). Se false con labels off → hero a tutta larghezza.
    var squareThumbnail: Bool = false

    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    @State private var loadedImage: UIImage?
    @State private var isLoading = false

    var body: some View {
        Group {
            if showsLabelsBelow {
                VStack(alignment: .leading, spacing: 6) {
                    heroFrame
                    VStack(alignment: .leading, spacing: 2) {
                        Text(vehicle.brand)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                            .lineLimit(1)
                        Text(vehicle.model)
                            .font(Typography.readingCardTitle)
                            .foregroundColor(.primaryText)
                            .lineLimit(1)
                        Text("\(vehicle.year)")
                            .font(Typography.readingCaption)
                            .foregroundColor(.accent)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                heroFrame
            }
        }
        .task(id: vehicle.heroImageURL?.absoluteString ?? vehicle.id) {
            await loadImage()
        }
        .onReceive(NotificationCenter.default.publisher(for: .evVehicleCatalogDidUpdate)) { _ in
            Task { await loadImage() }
        }
    }

    private var heroFrame: some View {
        let width: CGFloat? = squareThumbnail ? height : nil
        return Color.clear
            .frame(width: width, height: height)
            .frame(maxWidth: squareThumbnail ? nil : .infinity)
            .overlay { heroContent }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .background(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .fill(heroBackgroundGradient)
            )
    }

    @ViewBuilder
    private var heroContent: some View {
        if let loadedImage {
            Image(uiImage: loadedImage)
                .resizable()
                .scaledToFill()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipped()
        } else if isLoading {
            ProgressView()
                .tint(.accent)
        } else {
            Image(systemName: vehicle.powertrain == .ice ? "car.side.fill" : "bolt.car.fill")
                .font(.system(size: squareThumbnail ? 22 : 34, weight: .medium))
                .foregroundStyle(Color.accent.opacity(0.8))
        }
    }

    private func loadImage() async {
        loadedImage = nil
        guard let url = vehicle.heroImageURL else {
            isLoading = false
            return
        }
        if url.host?.contains("source.unsplash.com") == true {
            isLoading = false
            return
        }
        isLoading = true
        loadedImage = await VehicleImageLoader.shared.image(for: url)
        isLoading = false
    }

    private var heroBackgroundGradient: LinearGradient {
        switch vehicle.powertrain {
        case .ice:
            return LinearGradient(
                colors: [Color.iceLine.opacity(0.2), Color.surfaceElevated],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .ev:
            return LinearGradient(
                colors: [Color.evLine.opacity(0.2), Color.surfaceElevated],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .phev:
            return LinearGradient(
                colors: [Color.iceLine.opacity(0.14), Color.evLine.opacity(0.14)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
    }
}

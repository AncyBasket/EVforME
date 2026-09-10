//
//  VehicleHeroImage.swift
//  EVforME?
//

import SwiftUI

/// Hero veicolo: foto remota solo se presente; altrimenti placeholder editoriale (monogramma + powertrain).
/// Nessuna richiesta rete quando `heroImageURL` è nil.
struct VehicleHeroImage: View {
    let vehicle: VehicleCatalogItem
    var height: CGFloat = 120
    var cornerRadius: CGFloat = 14
    var showsLabelsBelow: Bool = true
    /// Miniatura quadrata (liste). Se false con labels off → hero a tutta larghezza.
    var squareThumbnail: Bool = false

    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    @Environment(\.accessibilityReduceTransparency) private var accessibilityReduceTransparency
    @Environment(\.colorScheme) private var colorScheme
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
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilitySummary)
        .task(id: vehicle.heroImageURL?.absoluteString ?? vehicle.id) {
            await loadImage()
        }
        .onReceive(NotificationCenter.default.publisher(for: .evVehicleCatalogDidUpdate)) { _ in
            Task { await loadImage() }
        }
    }

    private var accessibilitySummary: String {
        "\(vehicle.displayName), \(powertrainLabel), \(vehicle.year)"
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
                    .fill(heroBackgroundFill)
            )
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .stroke(Color.hairlineBorder, lineWidth: loadedImage == nil ? 1 : 0)
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
            placeholderContent
        }
    }

    private var placeholderContent: some View {
        ZStack(alignment: .topTrailing) {
            // Soft brand wash (hash stabile) + powertrain tint.
            LinearGradient(
                colors: placeholderGradientColors,
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .opacity(accessibilityReduceTransparency ? 1 : 0.95)

            // Generic car silhouette — not a real model photo.
            Image(systemName: silhouetteSymbol)
                .font(.system(size: squareThumbnail ? 28 : 44, weight: .light))
                .foregroundStyle(powertrainTint.opacity(0.22))
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: squareThumbnail ? .center : .bottomTrailing)
                .padding(squareThumbnail ? 8 : 14)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: squareThumbnail ? 6 : 10) {
                HStack(alignment: .center, spacing: 10) {
                    monogramBadge
                    if !squareThumbnail {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(vehicle.brand)
                                .font(Typography.readingCaption.weight(.semibold))
                                .foregroundStyle(Color.ink)
                                .lineLimit(1)
                            Text(truncatedModel)
                                .font(Typography.title2)
                                .foregroundStyle(Color.ink)
                                .lineLimit(1)
                                .minimumScaleFactor(0.75)
                        }
                        Spacer(minLength: 0)
                    }
                }

                if squareThumbnail {
                    Text(truncatedModel)
                        .font(Typography.readingCaption.weight(.semibold))
                        .foregroundStyle(Color.ink)
                        .lineLimit(2)
                        .minimumScaleFactor(0.8)
                }

                Spacer(minLength: 0)

                powertrainChip
            }
            .padding(squareThumbnail ? 8 : 12)
        }
    }

    private var monogramBadge: some View {
        Text(brandMonogram)
            .font(.system(size: squareThumbnail ? 13 : 18, weight: .bold, design: .serif))
            .foregroundStyle(Color.ink)
            .frame(width: squareThumbnail ? 32 : 44, height: squareThumbnail ? 32 : 44)
            .background(
                Circle()
                    .fill(brandAccent.opacity(accessibilityReduceTransparency ? 0.35 : 0.28))
            )
            .overlay(
                Circle()
                    .stroke(Color.ink.opacity(0.12), lineWidth: 1)
            )
            .accessibilityHidden(true)
    }

    private var powertrainChip: some View {
        Text(powertrainLabel.uppercased())
            .font(.system(size: squareThumbnail ? 9 : 11, weight: .bold))
            .tracking(0.6)
            .foregroundStyle(Color.ink)
            .padding(.horizontal, squareThumbnail ? 6 : 8)
            .padding(.vertical, squareThumbnail ? 3 : 5)
            .background(powertrainTint.opacity(0.85))
            .clipShape(RoundedRectangle(cornerRadius: 2, style: .continuous))
            .accessibilityHidden(true)
    }

    private var brandMonogram: String {
        let parts = vehicle.brand
            .split(whereSeparator: { !$0.isLetter })
            .map(String.init)
            .filter { !$0.isEmpty }
        if parts.count >= 2, let a = parts[0].first, let b = parts[1].first {
            return "\(a)\(b)".uppercased()
        }
        let compact = vehicle.brand.filter(\.isLetter)
        return String(compact.prefix(2)).uppercased()
    }

    private var truncatedModel: String {
        let model = vehicle.model.trimmingCharacters(in: .whitespacesAndNewlines)
        let limit = squareThumbnail ? 18 : 28
        guard model.count > limit else { return model }
        return String(model.prefix(limit - 1)) + "…"
    }

    private var powertrainLabel: String {
        switch vehicle.powertrain {
        case .ice: return L10n.powertrainICE
        case .ev: return L10n.powertrainEV
        case .phev: return L10n.powertrainPHEV
        }
    }

    private var powertrainTint: Color {
        switch vehicle.powertrain {
        case .ice: return .iceLine
        case .ev: return .evLine
        case .phev: return .accent
        }
    }

    private var silhouetteSymbol: String {
        switch vehicle.powertrain {
        case .ice: return "car.side.fill"
        case .ev: return "bolt.car.fill"
        case .phev: return "car.fill"
        }
    }

    /// Accento marca stabile (hash del nome) — niente asset per marca.
    private var brandAccent: Color {
        var hash: UInt64 = 5381
        for scalar in vehicle.brand.uppercased().unicodeScalars {
            hash = ((hash << 5) &+ hash) &+ UInt64(scalar.value)
        }
        let hue = Double(hash % 360) / 360.0
        let brightness = colorScheme == .dark ? 0.58 : 0.72
        return Color(hue: hue, saturation: 0.42, brightness: brightness)
    }

    private var placeholderGradientColors: [Color] {
        let base = accessibilityReduceTransparency ? Color.surfaceElevated : Color.surfaceElevated.opacity(0.95)
        return [
            brandAccent.opacity(colorScheme == .dark ? 0.28 : 0.18),
            powertrainTint.opacity(0.12),
            base
        ]
    }

    private var heroBackgroundFill: LinearGradient {
        if accessibilityReduceTransparency {
            return LinearGradient(
                colors: [Color.surfaceElevated, Color.surfaceElevated],
                startPoint: .top,
                endPoint: .bottom
            )
        }
        return heroBackgroundGradient
    }

    private func loadImage() async {
        loadedImage = nil
        guard let url = vehicle.heroImageURL else {
            isLoading = false
            return
        }
        // Block known non-licensed / unstable hosts even if a URL sneaks in.
        // Wikimedia Commons / upload.wikimedia.org allowed only for pipeline-applied CC0/PD URLs.
        let host = url.host?.lowercased() ?? ""
        let blocked = ["edidomus", "quattroruote", "source.unsplash.com", "images.unsplash.com", "catbox"]
        if blocked.contains(where: { host.contains($0) }) {
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

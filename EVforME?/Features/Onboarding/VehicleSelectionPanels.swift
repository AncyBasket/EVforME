//
//  VehicleSelectionPanels.swift
//  EVforME?
//

import SwiftUI

/// Due auto come pezzi di un confronto fotografico, non card prodotto.
struct VehiclePickPairSection: View {
    let sourceVehicle: VehicleCatalogItem?
    let targetVehicle: VehicleCatalogItem?
    let sourceDimensionsText: String
    let targetDimensionsText: String
    var onSourceTap: () -> Void
    var onTargetTap: () -> Void

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 12) {
                pickPanel(
                    role: .source,
                    title: L10n.sourceVehicleLabel,
                    vehicle: sourceVehicle,
                    dimensionsLine: sourceDimensionsText,
                    action: onSourceTap
                )
                pickPanel(
                    role: .target,
                    title: L10n.targetVehicleLabel,
                    vehicle: targetVehicle,
                    dimensionsLine: targetDimensionsText,
                    action: onTargetTap
                )
            }
            .frame(minWidth: 340)

            VStack(spacing: 14) {
                pickPanel(
                    role: .source,
                    title: L10n.sourceVehicleLabel,
                    vehicle: sourceVehicle,
                    dimensionsLine: sourceDimensionsText,
                    action: onSourceTap
                )
                pickPanel(
                    role: .target,
                    title: L10n.targetVehicleLabel,
                    vehicle: targetVehicle,
                    dimensionsLine: targetDimensionsText,
                    action: onTargetTap
                )
            }
        }
    }

    private enum PanelRole {
        case source, target
    }

    private func badge(for vehicle: VehicleCatalogItem?, role: PanelRole) -> (text: String, tint: Color) {
        switch vehicle?.powertrain {
        case .ice:
            return (L10n.powertrainICE, Color.iceLine)
        case .ev:
            return (L10n.powertrainEV, Color.evLine)
        case .phev:
            return (L10n.powertrainPHEV, Color.accent)
        case .none:
            return (role == .source ? L10n.powertrainICE : L10n.powertrainEV, role == .source ? Color.iceLine : Color.evLine)
        }
    }

    private func pickPanel(
        role: PanelRole,
        title: String,
        vehicle: VehicleCatalogItem?,
        dimensionsLine: String,
        action: @escaping () -> Void
    ) -> some View {
        let badge = badge(for: vehicle, role: role)
        return Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                ZStack(alignment: .bottomLeading) {
                    if let vehicle {
                        VehicleHeroImage(
                            vehicle: vehicle,
                            height: 148,
                            cornerRadius: 0,
                            showsLabelsBelow: false,
                            squareThumbnail: false
                        )
                    } else {
                        Rectangle()
                            .fill(Color.ink.opacity(0.06))
                            .frame(maxWidth: .infinity)
                            .frame(height: 148)
                            .overlay(
                                Text(L10n.vehiclePairTapToChoose)
                                    .font(Typography.readingCaption)
                                    .foregroundStyle(Color.secondaryText)
                                    .padding(12)
                            )
                    }

                    Text(badge.text)
                        .font(Typography.sectionEyebrow)
                        .tracking(1.2)
                        .foregroundStyle(Color.ink)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .background(Color.accent)
                        .accessibilityHidden(true)
                        .padding(10)
                }
                .frame(height: 148)
                .clipped()
                .overlay(alignment: .bottom) {
                    Rectangle()
                        .fill(vehicle == nil ? Color.hairlineBorder : badge.tint)
                        .frame(height: 2)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(title.uppercased())
                        .font(Typography.sectionEyebrow)
                        .foregroundStyle(Color.secondaryText)
                        .tracking(0.8)
                    if let vehicle {
                        Text(vehicle.brand)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                            .lineLimit(1)
                        Text(vehicle.model)
                            .font(Typography.title2)
                            .foregroundColor(.ink)
                            .lineLimit(1)
                        Text("\(vehicle.year)")
                            .font(Typography.readingCaption)
                            .foregroundColor(badge.tint)
                    } else {
                        Text(L10n.vehicleNotSelected)
                            .font(Typography.title2)
                            .foregroundColor(.secondaryText)
                    }
                    Text(dimensionsLine)
                        .font(.system(size: 11, weight: .regular))
                        .foregroundColor(.secondaryText)
                        .lineLimit(1)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(title). \(vehicle?.displayName ?? L10n.vehicleNotSelected). \(badge.text)")
        .accessibilityHint(L10n.vehiclePairTapToChoose)
    }
}

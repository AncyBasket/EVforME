//
//  VerdictShareCard.swift
//  EVforME?
//

import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct VerdictShareCardView: View {
    let result: SimulationResult
    let input: UserInput

    private let ink = Color(red: 0.07, green: 0.08, blue: 0.07)
    private let muted = Color(red: 0.35, green: 0.38, blue: 0.34)
    private let stone = Color(red: 0.925, green: 0.933, blue: 0.910)
    private let volt = Color(red: 0.72, green: 0.92, blue: 0.18)

    private var sourceName: String {
        VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.displayName ?? L10n.currentVehicleShort
    }

    private var targetName: String {
        VehicleCatalogService.shared.vehicle(by: input.targetVehicleId)?.displayName ?? L10n.electrifiedVehicleShort
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("EVforME?")
                    .font(.system(size: 15, weight: .bold, design: .serif))
                    .foregroundStyle(ink)
                    .tracking(0.8)
                Spacer()
                Text(L10n.shareCardEyebrow.uppercased())
                    .font(.system(size: 10, weight: .semibold, design: .default))
                    .foregroundStyle(muted)
                    .tracking(1.2)
            }
            .padding(.bottom, 22)

            Rectangle()
                .fill(volt)
                .frame(width: 48, height: 5)
                .padding(.bottom, 18)

            Text(result.verdict.title)
                .font(.system(size: 42, weight: .bold, design: .serif))
                .foregroundStyle(ink)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, 10)

            Text(result.verdict.description)
                .font(.system(size: 15, weight: .regular, design: .default))
                .foregroundStyle(muted)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, 22)

            Text(L10n.verdictCompareLine(sourceName, targetName))
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(muted)
                .padding(.bottom, 18)

            VStack(alignment: .leading, spacing: 0) {
                shareMetricRow(
                    label: L10n.verdictProofSavingsLabel,
                    value: L10n.verdictProofSavingsValue(
                        result.yearlySavingsRange.lowerBound,
                        result.yearlySavingsRange.upperBound
                    )
                )
                shareMetricRow(
                    label: L10n.verdictProofChargesLabel,
                    value: "\(result.weeklyCharges)× / \(L10n.shareCardWeekShort)"
                )
                if let months = result.breakEvenMonths {
                    shareMetricRow(
                        label: L10n.verdictProofBreakEvenLabel,
                        value: L10n.verdictProofBreakEvenValue(months),
                        emphasize: true
                    )
                }
            }

            Spacer(minLength: 20)

            Text("\(L10n.yearlyKmValue(input.dailyKm)) · \(input.tripProfile.title)")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(muted)
        }
        .padding(28)
        .frame(width: 390, height: 520, alignment: .leading)
        .background(stone)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(volt)
                .frame(width: 5)
        }
    }

    private func shareMetricRow(label: String, value: String, emphasize: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(muted)
                .tracking(0.6)
            Spacer(minLength: 12)
            Text(value)
                .font(.system(size: emphasize ? 16 : 15, weight: .semibold, design: .serif))
                .foregroundStyle(ink)
        }
        .padding(.vertical, 11)
        .overlay(alignment: .bottom) {
            Rectangle().fill(ink.opacity(0.10)).frame(height: 1)
        }
    }
}

enum VerdictShareCardRenderer {
    @MainActor
    static func makeCard(result: SimulationResult, input: UserInput) -> ShareableVerdictCard? {
        let view = VerdictShareCardView(result: result, input: input)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 3
        guard let image = renderer.uiImage else { return nil }
        return ShareableVerdictCard(image: image)
    }
}

struct ShareableVerdictCard: Transferable {
    let image: UIImage

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .png) { card in
            card.image.pngData() ?? Data()
        }
    }
}

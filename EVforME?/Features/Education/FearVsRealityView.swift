//
//  FearVsRealityView.swift
//  EVforME?
//

import SwiftUI

struct FearVsRealityView: View {
    let fearRealityItems: [FearRealityItem]
    @State private var appear: Bool = false
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(fearRealityItems.enumerated()), id: \.1.id) { index, item in
                fearItem(fear: item.fear, reality: item.reality)
                    .opacity(appear ? 1 : 0)
                    .offset(y: appear ? 0 : (accessibilityReduceMotion ? 0 : 8))
                    .animation(rowAppearAnimation(delay: Double(index) * 0.06), value: appear)

                if index < fearRealityItems.count - 1 {
                    Rectangle()
                        .fill(Color.hairlineBorder)
                        .frame(height: 1)
                        .padding(.vertical, 14)
                }
            }
        }
        .onAppear { appear = true }
    }

    private func rowAppearAnimation(delay: Double) -> Animation {
        accessibilityReduceMotion ? .easeOut(duration: 0.16) : .easeOut(duration: 0.4).delay(delay)
    }

    private func fearItem(fear: String, reality: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.fearEyebrow.uppercased())
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.8)
            Text(fear)
                .font(Typography.title2)
                .foregroundColor(.ink)
            Text(L10n.realityEyebrow.uppercased())
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.8)
                .padding(.top, 4)
            Text(reality)
                .font(Typography.readingBody)
                .foregroundColor(.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(L10n.fearEyebrow): \(fear). \(L10n.realityEyebrow): \(reality)")
    }
}

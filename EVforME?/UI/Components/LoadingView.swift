//
//  LoadingView.swift
//  EVforME?
//

import SwiftUI

struct LoadingView: View {
    @State private var pulse = false
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    var body: some View {
        ZStack {
            Color.appScreenBackground.opacity(0.92)
                .ignoresSafeArea()

            VStack(spacing: 20) {
                Text(L10n.appTitle)
                    .font(Typography.sectionEyebrow)
                    .foregroundStyle(Color.ink)
                    .tracking(1.0)

                Capsule()
                    .fill(Color.accent)
                    .frame(width: pulse ? 72 : 32, height: 5)

                Text(L10n.calculating)
                    .font(Typography.readingIntro)
                    .foregroundStyle(Color.ink)

                Text(L10n.calculatingSubtitle)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 32)
        }
        .onAppear {
            guard !accessibilityReduceMotion else {
                pulse = true
                return
            }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                pulse = true
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(L10n.calculating). \(L10n.calculatingSubtitle)")
    }
}

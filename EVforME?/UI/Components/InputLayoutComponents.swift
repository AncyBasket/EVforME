//
//  InputLayoutComponents.swift
//  EVforME?
//

import SwiftUI

struct InputSectionHeader: View {
    let step: Int
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(Typography.title)
                .foregroundColor(.ink)
                .accessibilityAddTraits(.isHeader)
            Text(subtitle)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct InputSectionCard<Content: View>: View {
    let step: Int
    let title: String
    let subtitle: String
    let appearIndex: Int
    let appearAnimation: Bool
    @ViewBuilder var content: () -> Content
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    private var appearAnimationStyle: Animation {
        if accessibilityReduceMotion {
            return .easeOut(duration: 0.2)
        }
        return .spring(response: 0.5, dampingFraction: 0.86).delay(Double(appearIndex) * 0.05)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            InputSectionHeader(step: step, title: title, subtitle: subtitle)
            content()
        }
        .opacity(appearAnimation ? 1 : 0)
        .offset(y: appearAnimation ? 0 : (accessibilityReduceMotion ? 0 : 14))
        .animation(appearAnimationStyle, value: appearAnimation)
    }
}

struct InputScreenHero: View {
    let appearAnimation: Bool
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    @State private var pulse = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.appTitle)
                .font(Typography.display)
                .foregroundStyle(Color.ink)
                .tracking(-0.5)
                .accessibilityAddTraits(.isHeader)

            Text(L10n.inputHeroSubtitle)
                .font(Typography.readingIntro)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)

            Capsule()
                .fill(Color.accent)
                .frame(width: pulse ? 64 : 44, height: 4)
                .accessibilityHidden(true)
        }
        .padding(.top, 10)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .opacity(appearAnimation ? 1 : 0)
        .offset(y: appearAnimation ? 0 : (accessibilityReduceMotion ? 0 : 10))
        .animation(
            accessibilityReduceMotion ? .easeOut(duration: 0.2) : .spring(response: 0.55, dampingFraction: 0.88),
            value: appearAnimation
        )
        .onAppear {
            guard !accessibilityReduceMotion else {
                pulse = true
                return
            }
            withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true)) {
                pulse = true
            }
        }
    }
}

//
//  PrimaryButton.swift
//  EVforME?
//

import SwiftUI

struct PrimaryButton: View {
    let title: String
    let action: () -> Void
    var accessibilityHint: String?

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(Typography.bodyBold)
                .tracking(0.3)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
                .background(Color.ctaFill)
                .foregroundStyle(Color.ctaLabel)
                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                .overlay(alignment: .bottom) {
                    Rectangle()
                        .fill(Color.accent)
                        .frame(height: 3)
                        .clipShape(RoundedRectangle(cornerRadius: 1, style: .continuous))
                }
        }
        .buttonStyle(.plain)
        .accessibleTouchTarget()
        .accessibilityLabel(title)
        .accessibilityHint(accessibilityHint ?? "")
        .accessibilityAddTraits(.isButton)
    }
}

#Preview {
    PrimaryButton(title: "Continua") {}
        .padding()
        .background(Color.appScreenBackground)
}

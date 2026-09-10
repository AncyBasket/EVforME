//
//  ImmersiveBackground.swift
//  EVforME?
//

import SwiftUI

/// Orizzonte pietra + alone volt in alto — una sola composizione, non dashboard.
struct ImmersiveBackground: View {
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    @State private var drift = false

    var body: some View {
        ZStack {
            Color.appScreenBackground

            LinearGradient(
                colors: colorScheme == .dark
                    ? [
                        Color(red: 0.14, green: 0.18, blue: 0.14),
                        Color.appScreenBackground,
                    ]
                    : [
                        Color(red: 0.86, green: 0.90, blue: 0.82),
                        Color.appScreenBackground,
                        Color(red: 0.90, green: 0.91, blue: 0.88),
                    ],
                startPoint: .top,
                endPoint: .bottom
            )

            Circle()
                .fill(Color.accent.opacity(colorScheme == .dark ? 0.16 : 0.28))
                .frame(width: 280, height: 280)
                .blur(radius: 70)
                .offset(x: drift ? 40 : -20, y: drift ? -80 : -120)
                .allowsHitTesting(false)

            VStack(spacing: 7) {
                ForEach(0..<40, id: \.self) { _ in
                    Rectangle()
                        .fill(Color.ink.opacity(colorScheme == .dark ? 0.03 : 0.025))
                        .frame(height: 1)
                }
            }
            .frame(maxHeight: .infinity, alignment: .top)
            .opacity(0.5)
            .allowsHitTesting(false)
        }
        .ignoresSafeArea()
        .onAppear {
            guard !accessibilityReduceMotion else { return }
            withAnimation(.easeInOut(duration: 7).repeatForever(autoreverses: true)) {
                drift = true
            }
        }
    }
}

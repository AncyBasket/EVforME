//
//  GlassChrome.swift
//  EVforME?
//
//  Liquid Glass (iOS 26+) con fallback e rispetto di Reduce Transparency.
//  Su iOS 27 il materiale di sistema migliora leggibilità / slider utente automaticamente.
//

import SwiftUI

extension View {
    /// Vetro di sistema se disponibile e se l’utente non ha “Riduci trasparenza”.
    @ViewBuilder
    func evGlassChrome(
        in shape: some Shape = RoundedRectangle(cornerRadius: 12, style: .continuous),
        fallback: Color = .surfaceElevated
    ) -> some View {
        modifier(EVGlassChromeModifier(shape: shape, fallback: fallback))
    }
}

private struct EVGlassChromeModifier<S: Shape>: ViewModifier {
    let shape: S
    let fallback: Color
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency

    func body(content: Content) -> some View {
        if reduceTransparency {
            content
                .background(fallback)
                .clipShape(shape)
        } else {
            content
                .glassEffect(.regular, in: shape)
        }
    }
}

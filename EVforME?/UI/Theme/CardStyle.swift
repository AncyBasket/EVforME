//
//  CardStyle.swift
//  EVforME?
//

import SwiftUI

extension View {
    /// Superficie quieta: niente card spesse — solo padding e hairline se serve interazione.
    func evCardStyle() -> some View {
        self
            .padding(.vertical, 4)
    }

    func evHighlightCardStyle() -> some View {
        self
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .fill(Color.accent.opacity(0.14))
            )
            .overlay(alignment: .leading) {
                Rectangle()
                    .fill(Color.accent)
                    .frame(width: 3)
            }
    }
}

extension View {
    func evNavigationChrome() -> some View {
        self
            .toolbarBackground(Color.appChrome, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
    }
}

struct InputNavigationChromeModifier: ViewModifier {
    let enabled: Bool

    func body(content: Content) -> some View {
        if enabled {
            content
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .principal) {
                        Text(L10n.appTitle)
                            .font(Typography.sectionEyebrow)
                            .foregroundColor(.ink)
                            .tracking(0.6)
                    }
                }
                .evNavigationChrome()
        } else {
            content
                .toolbar(.hidden, for: .navigationBar)
        }
    }
}

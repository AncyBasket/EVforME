//
//  Colors.swift
//  EVforME?
//
//  Identità “Ink & Volt”: pietra chiara, inchiostro, segnale lime — niente teal showroom.
//

import SwiftUI

extension Color {
    static let background = Color(uiColor: .systemBackground)
    static let primaryText = Color(uiColor: UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(white: 0.96, alpha: 1)
            : UIColor(red: 0.07, green: 0.08, blue: 0.07, alpha: 1)
    })
    static let secondaryText = Color(uiColor: UIColor { traits in
        traits.userInterfaceStyle == .dark
            ? UIColor(white: 0.72, alpha: 1)
            : UIColor(red: 0.35, green: 0.38, blue: 0.34, alpha: 1)
    })
    static let cardBackground = Color(uiColor: .secondarySystemGroupedBackground)

    /// Pietra fredda (non crema terracotta).
    static var appScreenBackground: Color {
        Color(uiColor: UIColor { traits in
            if traits.userInterfaceStyle == .dark {
                return UIColor(red: 0.08, green: 0.09, blue: 0.08, alpha: 1)
            }
            return UIColor(red: 0.925, green: 0.933, blue: 0.910, alpha: 1)
        })
    }

    static var appChrome: Color {
        Color(uiColor: UIColor { traits in
            if traits.userInterfaceStyle == .dark {
                return UIColor(red: 0.10, green: 0.11, blue: 0.10, alpha: 0.94)
            }
            return UIColor(red: 0.945, green: 0.950, blue: 0.935, alpha: 0.92)
        })
    }

    static var surfaceElevated: Color {
        Color(uiColor: UIColor { traits in
            if traits.userInterfaceStyle == .dark {
                return UIColor(red: 0.14, green: 0.15, blue: 0.13, alpha: 1)
            }
            return UIColor(red: 0.98, green: 0.985, blue: 0.97, alpha: 1)
        })
    }

    static var hairlineBorder: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(white: 1, alpha: 0.12)
                : UIColor(red: 0.12, green: 0.14, blue: 0.11, alpha: 0.14)
        })
    }

    /// Alias legacy → hairline (niente stroke “brutale”).
    static var brutalInk: Color { hairlineBorder }

    /// Inchiostro pieno (testo). In dark mode è chiaro.
    static var ink: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(white: 0.96, alpha: 1)
                : UIColor(red: 0.07, green: 0.08, blue: 0.07, alpha: 1)
        })
    }

    /// Fondo CTA sempre scuro (non si inverte in dark mode).
    static let ctaFill = Color(red: 0.07, green: 0.08, blue: 0.07)
    /// Testo CTA ad alto contrasto sul fill scuro.
    static let ctaLabel = Color.white

    /// Alias legacy → ink soft (niente teal showroom).
    static let accentSecondary = Color(red: 0.12, green: 0.14, blue: 0.12)
    static let accentDark = Color(red: 0.10, green: 0.12, blue: 0.10)
    static let accentLight = Color(red: 0.85, green: 0.96, blue: 0.45)

    static var accentGradient: LinearGradient {
        LinearGradient(
            colors: [accent, Color(red: 0.55, green: 0.82, blue: 0.12)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    static var accentSecondaryGradient: LinearGradient {
        LinearGradient(
            colors: [accentDark, Color(red: 0.18, green: 0.20, blue: 0.17)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    static var heroGlowGradient: RadialGradient {
        RadialGradient(
            colors: [accent.opacity(0.22), Color.clear],
            center: .topTrailing,
            startRadius: 10,
            endRadius: 280
        )
    }

    static var softBackgroundGradient: LinearGradient {
        LinearGradient(
            colors: [
                accent.opacity(0.18),
                Color.clear,
            ],
            startPoint: .top,
            endPoint: .center
        )
    }

    static let success = Color(red: 0.22, green: 0.62, blue: 0.38)
    static let successLight = Color(red: 0.22, green: 0.62, blue: 0.38).opacity(0.14)
    static let warning = Color(red: 0.86, green: 0.42, blue: 0.18)
    static let warningLight = Color(red: 0.86, green: 0.42, blue: 0.18).opacity(0.14)

    static let iceLine = Color(red: 0.86, green: 0.42, blue: 0.22)
    static let evLine = Color(red: 0.18, green: 0.55, blue: 0.40)
}

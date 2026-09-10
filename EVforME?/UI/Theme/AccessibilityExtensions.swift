//
//  AccessibilityExtensions.swift
//  EVforME?
//
//  Helper accessibilità usati da bottoni e grafici.
//

import SwiftUI

extension View {
    /// Touch target minimo 44×44pt.
    func accessibleTouchTarget() -> some View {
        self.frame(minWidth: 44, minHeight: 44)
    }

    /// Descrizione VoiceOver per grafici.
    func accessibleChartDescription(
        title: String,
        summary: String,
        dataDescription: String
    ) -> some View {
        self
            .accessibilityElement(children: .combine)
            .accessibilityLabel(title)
            .accessibilityValue(summary)
            .accessibilityHint(dataDescription)
    }
}

struct AccessibilityHelper {
    static func costDescription(amount: Double, currency: String = "€") -> String {
        String(format: "%@%.2f", currency, amount)
    }

    static func percentageDescription(value: Double) -> String {
        "\(Int(value * 100))%"
    }

    static func vehicleDescription(brand: String, model: String, year: Int) -> String {
        "\(brand) \(model), anno \(year)"
    }

    static func verdictDescription(verdict: EVVerdict) -> String {
        switch verdict {
        case .yes:
            return "Verdetto positivo: il passaggio a EV è conveniente"
        case .maybe:
            return "Verdetto incerto: il passaggio a EV potrebbe essere conveniente"
        case .notYet:
            return "Verdetto negativo: il passaggio a EV non è ancora conveniente"
        }
    }
}

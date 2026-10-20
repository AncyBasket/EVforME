//
//  TimeEvolutionView.swift
//  EVforME?
//

import SwiftUI

struct TimeEvolutionView: View {
    let scenario: Scenario
    var yearlyComparison: [YearlyComparison] = []

    private var lines: [String] {
        let derived = Scenario.derivedTimeline(from: yearlyComparison)
        return derived.isEmpty ? scenario.timelineText : derived
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if !lines.isEmpty {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(Array(lines.enumerated()), id: \.offset) { index, text in
                        HStack(alignment: .top, spacing: 12) {
                            Text(String(format: "%02d", index + 1))
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.ink)
                                .frame(width: 28, alignment: .leading)
                            Text(text)
                                .font(Typography.readingBody)
                                .foregroundColor(.secondaryText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }

            Text(L10n.timeMessage)
                .font(Typography.readingIntro)
                .foregroundColor(.ink)
                .padding(.top, 4)
        }
    }
}

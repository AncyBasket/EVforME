//
//  CostSectionView.swift
//  EVforME?
//

import SwiftUI

struct CostSectionView: View {
    let result: SimulationResult
    let scenario: Scenario

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(L10n.costsOverTimeIntro)
                .font(Typography.readingIntro)
                .foregroundColor(.secondaryText)

            if result.yearlyComparison.isEmpty {
                Text(L10n.assumptionCalculationsEstimates)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
            } else {
                YearlyCostComparisonChart(comparison: result.yearlyComparison)
                costsTable(comparison: result.yearlyComparison)
                if let last = result.yearlyComparison.last {
                    let savings = Int(last.gasCost - last.evCost)
                    Text(L10n.calculationSavings(last.year, savings))
                        .font(Typography.title2)
                        .foregroundColor(.ink)
                        .padding(.top, 4)
                        .overlay(alignment: .leading) {
                            Rectangle()
                                .fill(Color.accent)
                                .frame(width: 3)
                                .padding(.leading, -10)
                        }
                }
            }
        }
    }

    private func costsTable(comparison: [YearlyComparison]) -> some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text("").frame(width: 52, alignment: .leading)
                Text(L10n.gasLabel)
                    .font(Typography.readingCaption)
                    .foregroundColor(.iceLine)
                    .frame(maxWidth: .infinity)
                Text(L10n.evLabel)
                    .font(Typography.readingCaption)
                    .foregroundColor(.evLine)
                    .frame(maxWidth: .infinity)
                Text(L10n.savings)
                    .font(Typography.readingCaption)
                    .foregroundColor(.ink)
                    .frame(maxWidth: .infinity)
            }
            .padding(.vertical, 10)
            .overlay(alignment: .bottom) {
                Rectangle().fill(Color.hairlineBorder).frame(height: 1)
            }

            ForEach(comparison, id: \.year) { year in
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(L10n.yearFormat(year.year))
                        .font(Typography.readingBody)
                        .foregroundColor(.ink)
                        .frame(width: 52, alignment: .leading)
                    Text("€\(Int(year.gasCost))")
                        .font(Typography.readingBody)
                        .foregroundColor(.iceLine)
                        .frame(maxWidth: .infinity)
                        .multilineTextAlignment(.center)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                    Text("€\(Int(year.evCost))")
                        .font(Typography.readingBody)
                        .foregroundColor(.evLine)
                        .frame(maxWidth: .infinity)
                        .multilineTextAlignment(.center)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                    Text("€\(Int(year.gasCost - year.evCost))")
                        .font(Typography.readingBody.weight(.semibold))
                        .foregroundColor(.ink)
                        .frame(maxWidth: .infinity)
                        .multilineTextAlignment(.center)
                        .lineLimit(1)
                        .minimumScaleFactor(0.72)
                }
                .padding(.vertical, 10)
                .overlay(alignment: .bottom) {
                    Rectangle().fill(Color.hairlineBorder.opacity(0.7)).frame(height: 1)
                }
            }
        }
    }
}

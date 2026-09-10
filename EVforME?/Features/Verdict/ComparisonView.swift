//
//  ComparisonView.swift
//  EVforME?
//

import SwiftUI

struct ComparisonView: View {
    let comparison: [YearlyComparison]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(L10n.comparison5Year)
                .font(Typography.title2)
                .foregroundColor(.ink)

            if !comparison.isEmpty {
                YearlyCostComparisonChart(comparison: comparison)
            }

            VStack(spacing: 0) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text("")
                        .frame(width: 52, alignment: .leading)
                    Text(L10n.gasLabel)
                        .font(Typography.readingCaption)
                        .foregroundColor(.iceLine)
                        .frame(maxWidth: .infinity)
                    Text(L10n.evLabel)
                        .font(Typography.readingCaption)
                        .foregroundColor(.evLine)
                        .frame(maxWidth: .infinity)
                }
                .padding(.vertical, 10)
                .overlay(alignment: .bottom) {
                    Rectangle().fill(Color.hairlineBorder).frame(height: 1)
                }

                ForEach(comparison, id: \.year) { year in
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(L10n.yearFormat(year.year))
                            .font(Typography.readingBody.weight(.semibold))
                            .foregroundColor(.ink)
                            .frame(width: 52, alignment: .leading)
                        Text("€\(Int(year.gasCost))")
                            .font(Typography.readingBody)
                            .foregroundColor(.iceLine)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)
                            .lineLimit(1)
                            .minimumScaleFactor(0.75)
                        Text("€\(Int(year.evCost))")
                            .font(Typography.readingBody)
                            .foregroundColor(.evLine)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)
                            .lineLimit(1)
                            .minimumScaleFactor(0.75)
                    }
                    .padding(.vertical, 10)
                    .overlay(alignment: .bottom) {
                        Rectangle().fill(Color.hairlineBorder.opacity(0.7)).frame(height: 1)
                    }
                }
            }
        }
    }
}

//
//  YearlyCostComparisonChart.swift
//  EVforME?
//

import Charts
import SwiftUI

/// Costi cumulativi: **barre affiancate** per anno (benzina vs elettrico), più leggibile del solo line chart.
struct YearlyCostComparisonChart: View {
    let comparison: [YearlyComparison]

    private var yMax: Double {
        comparison.map { max($0.gasCost, $0.evCost) }.max() ?? 1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text(L10n.costsChartTitle)
                    .font(Typography.readingCardTitle)
                    .foregroundColor(.primaryText)
                Spacer()
                HStack(spacing: 14) {
                    chartLegendDot(color: .iceLine, title: L10n.gasLabel)
                    chartLegendDot(color: .evLine, title: L10n.evLabel)
                }
            }

            Chart {
                ForEach(comparison, id: \.year) { row in
                    BarMark(
                        x: .value(L10n.chartAxisOwnershipYear, row.year),
                        y: .value(L10n.chartAxisCumulativeCost, row.gasCost),
                        width: .ratio(0.32)
                    )
                    .foregroundStyle(Color.iceLine)
                    .position(by: .value(L10n.chartSeries, L10n.gasLabel))
                }
                ForEach(comparison, id: \.year) { row in
                    BarMark(
                        x: .value(L10n.chartAxisOwnershipYear, row.year),
                        y: .value(L10n.chartAxisCumulativeCost, row.evCost),
                        width: .ratio(0.32)
                    )
                    .foregroundStyle(Color.evLine)
                    .position(by: .value(L10n.chartSeries, L10n.evLabel))
                }
            }
            .frame(height: 240)
            .chartYScale(domain: 0...(yMax * 1.12))
            .chartPlotStyle { plot in
                plot.padding(.horizontal, 8)
            }
            .chartXAxis {
                AxisMarks(values: comparison.map(\.year)) { value in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [3, 4]))
                        .foregroundStyle(Color.secondaryText.opacity(0.2))
                    AxisValueLabel {
                        if let y = value.as(Int.self) {
                            yearAxisLabel(year: y)
                        } else if let y = value.as(Double.self) {
                            yearAxisLabel(year: Int(y.rounded()))
                        }
                    }
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading, values: .automatic(desiredCount: 5)) { value in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [3, 4]))
                        .foregroundStyle(Color.secondaryText.opacity(0.2))
                    AxisValueLabel {
                        if let v = value.as(Double.self) {
                            Text(Self.compactEuroAxisLabel(v))
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .lineLimit(1)
                                .minimumScaleFactor(0.75)
                        }
                    }
                }
            }
            .chartLegend(.hidden)
            .accessibilityLabel(L10n.costsChartA11ySummary)
            .accessibilityHint(L10n.costsChartA11yHint)
            .accessibleChartDescription(
                title: L10n.costsChartTitle,
                summary: L10n.costsChartA11ySummary,
                dataDescription: L10n.costsChartFootnote
            )

            Text(L10n.costsChartFootnote)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
        }
        .padding(.vertical, 8)
        // open layout: niente card intorno al grafico
    }

    private static func compactEuroAxisLabel(_ value: Double) -> String {
        let v = abs(value)
        if v >= 1_000_000 {
            return String(format: "%.1fM €", value / 1_000_000)
        }
        if v >= 100_000 {
            return String(format: "%.0fk €", value / 1_000)
        }
        if v >= 10_000 {
            return String(format: "%.0fk €", value / 1_000)
        }
        return "€\(Int(value))"
    }

    @ViewBuilder
    private func yearAxisLabel(year: Int) -> some View {
        Text(L10n.yearFormat(year))
            .font(Typography.readingCaption)
            .foregroundColor(.secondaryText)
            .lineLimit(1)
            .minimumScaleFactor(0.85)
    }

    private func chartLegendDot(color: Color, title: String) -> some View {
        HStack(spacing: 6) {
            RoundedRectangle(cornerRadius: 3, style: .continuous)
                .fill(color)
                .frame(width: 12, height: 12)
            Text(title)
                .font(Typography.readingCaption)
                .foregroundColor(.primaryText)
        }
    }
}

#Preview {
    YearlyCostComparisonChart(
        comparison: (1...5).map { YearlyComparison(year: $0, gasCost: Double($0) * 1800, evCost: Double($0) * 950) }
    )
    .padding()
    .background(Color.background)
}

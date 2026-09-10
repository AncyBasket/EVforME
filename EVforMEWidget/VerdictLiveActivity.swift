//
//  VerdictLiveActivity.swift
//  EVforMEWidget
//

import ActivityKit
import SwiftUI
import WidgetKit

struct VerdictLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: VerdictActivityAttributes.self) { context in
            lockScreenView(context: context)
                .activityBackgroundTint(Color(red: 0.925, green: 0.933, blue: 0.910))
                .activitySystemActionForegroundColor(Color(red: 0.07, green: 0.08, blue: 0.07))
                .widgetURL(URL(string: "evforme://verdict"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(WidgetL10n.brandShort)
                            .font(.caption2.weight(.heavy))
                        Text(context.state.title)
                            .font(.headline.weight(.black))
                            .lineLimit(2)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("€\(context.state.savingsMin)–\(context.state.savingsMax)")
                            .font(.caption.weight(.bold))
                        Text(WidgetL10n.chargesPerWeek(context.state.weeklyCharges))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        Text(WidgetL10n.kmPerYear(context.attributes.yearlyKm))
                            .font(.caption2)
                        Spacer()
                        if let months = context.state.breakEvenMonths {
                            Text(WidgetL10n.breakEvenMonths(months))
                                .font(.caption2.weight(.semibold))
                        }
                        Text(WidgetL10n.fuelPrice(context.state.fuelPrice))
                            .font(.caption2.weight(.semibold))
                    }
                    .padding(.top, 4)
                }
            } compactLeading: {
                Image(systemName: "bolt.car.fill")
                    .font(.caption.weight(.bold))
            } compactTrailing: {
                Text(context.state.title)
                    .font(.caption2.weight(.heavy))
                    .lineLimit(1)
            } minimal: {
                Image(systemName: "bolt.car.fill")
            }
            .widgetURL(URL(string: "evforme://verdict"))
        }
    }

    @ViewBuilder
    private func lockScreenView(context: ActivityViewContext<VerdictActivityAttributes>) -> some View {
        HStack(alignment: .center, spacing: 12) {
            RoundedRectangle(cornerRadius: 4, style: .continuous)
                .fill(Color.black)
                .frame(width: 4)

            VStack(alignment: .leading, spacing: 4) {
                Text(WidgetL10n.brandFull)
                    .font(.caption2.weight(.heavy))
                    .foregroundStyle(.black.opacity(0.65))
                Text(context.state.title)
                    .font(.headline.weight(.black))
                    .foregroundStyle(.black)
                    .lineLimit(2)
                Text(WidgetL10n.savingsChargesLine(
                    min: context.state.savingsMin,
                    max: context.state.savingsMax,
                    charges: context.state.weeklyCharges
                ))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.black.opacity(0.75))
            }
            Spacer(minLength: 0)
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(context.attributes.yearlyKm)")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.black)
                Text(WidgetL10n.kmPerYearLabel)
                    .font(.caption2)
                    .foregroundStyle(.black.opacity(0.6))
            }
        }
        .padding(14)
    }
}

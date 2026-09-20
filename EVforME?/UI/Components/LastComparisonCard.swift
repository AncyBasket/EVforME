//
//  LastComparisonCard.swift
//  EVforME?
//
//  Card home “Ultimo confronto” — retention loop 1.1.
//

import SwiftUI

struct LastComparisonCard: View {
    let snapshot: SavedScenarioSnapshot
    let deltaBadge: String?
    let dataFreshness: String
    var onReopen: () -> Void
    var onRecalculate: () -> Void
    var onRestoreForm: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text(L10n.lastComparisonTitle)
                    .font(Typography.readingCardTitle)
                    .foregroundStyle(Color.primaryText)
                Spacer(minLength: 8)
                Text(snapshot.createdDate, style: .date)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            }

            Text(snapshot.pairLabel)
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)

            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(snapshot.verdictTitle)
                    .font(Typography.bodyBold)
                    .foregroundStyle(Color.ink)
                Text("€\(snapshot.savingsMin)–€\(snapshot.savingsMax)/anno")
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            }

            if let deltaBadge {
                Text(deltaBadge)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Text(dataFreshness)
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)

            HStack(spacing: 10) {
                button(L10n.lastComparisonReopen, action: onReopen)
                button(L10n.lastComparisonRecalculate, action: onRecalculate)
            }

            Button(action: onRestoreForm) {
                Text(L10n.lastComparisonRestoreForm)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.accentDark)
            }
            .buttonStyle(.plain)
            .accessibilityHint(L10n.historyRestoreHint)
        }
        .evHighlightCardStyle()
        .accessibilityElement(children: .contain)
    }

    private func button(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(Typography.readingCaption)
                .fontWeight(.semibold)
                .foregroundStyle(Color.ctaLabel)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(Color.ctaFill)
                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

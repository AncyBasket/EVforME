//
//  ApprofondimentiView.swift
//  EVforME?
//

import SwiftUI

struct ApprofondimentiView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            subsection(title: L10n.subsectionWhereNumbersTitle, body: L10n.subsectionWhereNumbersBody)
            subsection(title: L10n.subsectionEnvironmentTitle, body: L10n.subsectionEnvironmentBody)
            subsection(title: L10n.subsectionBatteryTitle, body: L10n.subsectionBatteryBody)
            VStack(alignment: .leading, spacing: 10) {
                subsection(title: L10n.subsectionIncentivesTitle, body: L10n.subsectionIncentivesBody)
                Link(destination: URL(string: "https://www.mise.gov.it/index.php/it/energia/trasporti/ecobonus-autovetture")!) {
                    HStack(spacing: 8) {
                        Text(L10n.incentivesLinkTitle)
                            .font(Typography.readingCardTitle)
                        Image(systemName: "arrow.up.right")
                            .font(.caption.weight(.semibold))
                    }
                    .foregroundColor(.ink)
                    .padding(.vertical, 10)
                    .overlay(alignment: .bottom) {
                        Rectangle()
                            .fill(Color.accent)
                            .frame(height: 2)
                    }
                }
                .accessibilityHint(L10n.incentivesLinkA11yHint)
            }
        }
    }

    private func subsection(title: String, body: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(Typography.title2)
                .foregroundColor(.ink)
            Text(body)
                .font(Typography.readingBody)
                .foregroundColor(.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

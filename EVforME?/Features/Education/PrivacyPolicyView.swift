//
//  PrivacyPolicyView.swift
//  EVforME?
//

import SwiftUI

struct PrivacyPolicyView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(L10n.privacyPolicyTitle)
                        .font(Typography.readingTitle)
                        .foregroundStyle(Color.ink)

                    Text(L10n.privacyPolicyUpdated)
                        .font(Typography.readingCaption)
                        .foregroundStyle(Color.secondaryText)

                    Text(L10n.privacyPolicyBody)
                        .font(Typography.readingBody)
                        .foregroundStyle(Color.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)

                    if let url = Defaults.privacyPolicyURL {
                        Button {
                            openURL(url)
                        } label: {
                            Text(L10n.privacyPolicyOpenWeb)
                                .font(Typography.bodyBold)
                                .foregroundStyle(Color.ink)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Color.accent.opacity(0.45))
                                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                        }
                        .buttonStyle(.plain)
                        .padding(.top, 8)
                    }
                }
                .padding(24)
            }
            .background(Color.appScreenBackground.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.guidesSheetClose) { dismiss() }
                }
            }
        }
    }
}

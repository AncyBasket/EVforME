//
//  LeadCaptureSheet.swift
//  EVforME?
//

import SwiftUI

struct LeadCaptureSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var email = ""
    @State private var city = ""
    @State private var consent = false
    @State private var isSending = false
    @State private var sendNote: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(L10n.leadSheetSubtitle)
                        .font(Typography.readingBody)
                        .foregroundColor(.secondaryText)
                }
                Section {
                    TextField(L10n.leadNamePlaceholder, text: $name)
                    TextField(L10n.leadEmailPlaceholder, text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                    TextField(L10n.leadCityPlaceholder, text: $city)
                }
                Section {
                    Toggle(L10n.leadConsentText, isOn: $consent)
                }
                if let sendNote {
                    Section {
                        Text(sendNote)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                    }
                }
            }
            .navigationTitle(L10n.leadSheetTitle)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(L10n.leadSend) {
                        Task { await submitLead() }
                    }
                    .disabled(!consent || email.isEmpty || isSending)
                }
            }
        }
    }

    private func submitLead() async {
        guard consent, !email.isEmpty else {
            sendNote = L10n.leadConsentRequired
            return
        }
        guard !Defaults.leadWebhookURL.isEmpty else {
            sendNote = L10n.leadSendUnavailable
            return
        }
        isSending = true
        defer { isSending = false }
        GrowthTracker.shared.track(.leadSubmitted, [
            "cityFilled": city.isEmpty ? "0" : "1",
            "emailFilled": email.isEmpty ? "0" : "1",
            "consent": consent ? "1" : "0",
        ])
        let remoteOK = await RemoteGrowthClient.postLead(
            name: name,
            email: email,
            city: city,
            consent: consent
        )
        sendNote = remoteOK ? L10n.leadSentRemote : L10n.leadSendFailed
        if remoteOK {
            try? await Task.sleep(nanoseconds: 450_000_000)
            dismiss()
        }
    }
}

//
//  GrowthDebugView.swift
//  EVforME?
//

import SwiftUI

#if DEBUG
import UIKit

struct GrowthDebugView: View {
    @State private var snapshot: [String: Int] = [:]
    @State private var exportedJSON: String = "[]"
    @State private var statusMessage: String = ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 12) {
                Text("Growth Funnel Snapshot")
                    .font(Typography.readingCardTitle)

                if snapshot.isEmpty {
                    Text("No events tracked yet.")
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                } else {
                    ForEach(snapshot.keys.sorted(), id: \.self) { key in
                        HStack {
                            Text(key)
                                .font(Typography.readingCaption)
                            Spacer()
                            Text("\(snapshot[key, default: 0])")
                                .font(Typography.readingCardTitle)
                        }
                    }
                }

                Divider().padding(.vertical, 4)

                HStack(spacing: 10) {
                    Button("Refresh") { reload() }
                        .buttonStyle(.bordered)
                    Button("Copy JSON") { copyJSON() }
                        .buttonStyle(.borderedProminent)
                        .tint(.accent)
                    Button("Clear Events") { clearEvents() }
                        .buttonStyle(.bordered)
                }

                if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .font(Typography.readingCaption)
                        .foregroundColor(.success)
                }

                Text("Events JSON")
                    .font(Typography.readingCardTitle)
                    .padding(.top, 8)

                ScrollView {
                    Text(exportedJSON)
                        .font(.system(.caption, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(12)
                        .background(Color.surfaceElevated)
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(Color.brutalInk, lineWidth: 1)
                        )
                }
            }
            .padding(16)
            .navigationTitle("Growth Debug")
            .onAppear(perform: reload)
        }
    }

    private func reload() {
        snapshot = GrowthTracker.shared.funnelSnapshot()
        exportedJSON = GrowthTracker.shared.exportEventsJSON()
        statusMessage = ""
    }

    private func copyJSON() {
        UIPasteboard.general.string = exportedJSON
        statusMessage = "JSON copied to clipboard."
    }

    private func clearEvents() {
        GrowthTracker.shared.clearEvents()
        reload()
        statusMessage = "Events cleared."
    }
}
#endif

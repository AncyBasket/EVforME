//
//  FreeReportSheet.swift
//  EVforME?
//

import SwiftUI

struct FreeReportSheet: View {
    @Environment(\.dismiss) private var dismiss
    let result: SimulationResult
    let userInput: UserInput
    @State private var pdfURL: URL?

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text(L10n.freeReportSubtitle)
                    .font(Typography.readingBody)
                    .foregroundColor(.secondaryText)
                Text("• \(L10n.reportIncluded1)")
                Text("• \(L10n.reportIncluded2)")
                Text("• \(L10n.reportIncluded3)")
                Text(L10n.freeReportBadge)
                    .font(Typography.readingCardTitle)
                    .foregroundColor(.success)
                    .padding(.top, 8)
                if let pdfURL {
                    ShareLink(item: pdfURL) {
                        Label(L10n.sharePDFReport, systemImage: "doc.richtext")
                    }
                    .buttonStyle(.bordered)
                }
                Spacer(minLength: 0)
                Button(L10n.exportPDFReport) {
                    GrowthTracker.shared.track(.reportRequested, [
                        "priceVariant": "included",
                    ])
                    pdfURL = try? PDFReportService.temporaryPDFURL(result: result, input: userInput)
                }
                .buttonStyle(.borderedProminent)
                .tint(.accent)
            }
            .padding(20)
            .navigationTitle(L10n.freeReportTitle)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.guidesSheetClose) { dismiss() }
                }
            }
            .onAppear {
                pdfURL = try? PDFReportService.temporaryPDFURL(result: result, input: userInput)
            }
        }
    }
}

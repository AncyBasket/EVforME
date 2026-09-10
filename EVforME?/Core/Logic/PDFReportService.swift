//
//  PDFReportService.swift
//  EVforME?
//
//  Report PDF allineato a Ink & Volt: inchiostro, segnale lime, tipografia serif.
//

import Foundation
import UIKit

enum PDFReportService {
    private static let ink = UIColor(red: 0.07, green: 0.08, blue: 0.07, alpha: 1)
    private static let volt = UIColor(red: 0.72, green: 0.92, blue: 0.18, alpha: 1)
    private static let stone = UIColor(red: 0.925, green: 0.933, blue: 0.910, alpha: 1)
    private static let muted = UIColor(red: 0.35, green: 0.38, blue: 0.34, alpha: 1)

    @MainActor
    static func makeReportPDF(result: SimulationResult, input: UserInput) -> Data {
        let pageRect = CGRect(x: 0, y: 0, width: 612, height: 792)
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect)
        return renderer.pdfData { ctx in
            ctx.beginPage()
            let cg = ctx.cgContext

            // Fondo pietra
            cg.setFillColor(stone.cgColor)
            cg.fill(pageRect)

            // Header inchiostro + striscia volt
            cg.setFillColor(ink.cgColor)
            cg.fill(CGRect(x: 0, y: 0, width: pageRect.width, height: 88))
            cg.setFillColor(volt.cgColor)
            cg.fill(CGRect(x: 0, y: 88, width: pageRect.width, height: 4))

            let brandFont = UIFont(name: "Georgia-Bold", size: 14)
                ?? UIFont.systemFont(ofSize: 14, weight: .bold)
            let titleFont = UIFont(name: "Georgia-Bold", size: 28)
                ?? UIFont.systemFont(ofSize: 28, weight: .bold)
            let sectionFont = UIFont.systemFont(ofSize: 12, weight: .semibold)
            let bodyFont = UIFont.systemFont(ofSize: 11, weight: .regular)

            let brandAttrs: [NSAttributedString.Key: Any] = [
                .font: brandFont,
                .foregroundColor: UIColor.white,
                .kern: 1.2,
            ]
            let titleAttrs: [NSAttributedString.Key: Any] = [
                .font: titleFont,
                .foregroundColor: UIColor.white,
            ]
            let sectionAttrs: [NSAttributedString.Key: Any] = [
                .font: sectionFont,
                .foregroundColor: ink,
                .kern: 0.6,
            ]
            let bodyAttrs: [NSAttributedString.Key: Any] = [
                .font: bodyFont,
                .foregroundColor: muted,
            ]

            ("EVforME?" as NSString).draw(at: CGPoint(x: 36, y: 22), withAttributes: brandAttrs)
            (result.verdict.title as NSString).draw(at: CGPoint(x: 36, y: 44), withAttributes: titleAttrs)

            var y: CGFloat = 112
            func drawSection(_ title: String, _ body: String) {
                // Accento volt a sinistra della sezione
                cg.setFillColor(volt.cgColor)
                cg.fill(CGRect(x: 36, y: y + 2, width: 3, height: 12))
                (title.uppercased() as NSString).draw(at: CGPoint(x: 46, y: y), withAttributes: sectionAttrs)
                y += 20
                let width = pageRect.width - 72
                let size = (body as NSString).boundingRect(
                    with: CGSize(width: width, height: 500),
                    options: [.usesLineFragmentOrigin, .usesFontLeading],
                    attributes: bodyAttrs,
                    context: nil
                )
                let rect = CGRect(x: 36, y: y, width: width, height: ceil(size.height) + 4)
                (body as NSString).draw(in: rect, withAttributes: bodyAttrs)
                y = rect.maxY + 20
            }

            drawSection(
                L10n.why,
                """
                \(result.verdict.description)

                \(L10n.impactSaveBetween(result.yearlySavingsRange.lowerBound, result.yearlySavingsRange.upperBound))
                \(L10n.impactChargePerWeek(result.weeklyCharges))
                \(result.breakEvenMonths.map { L10n.breakEvenMonthsBadge($0) } ?? L10n.breakEvenNotReachedReason)

                \(result.keyReasons.map { "• \($0)" }.joined(separator: "\n"))
                """
            )

            drawSection(
                L10n.purchasePricesTitle,
                """
                \(L10n.sourcePurchasePriceLabel): €\(Int(input.sourcePurchasePrice))
                \(L10n.targetPurchasePriceLabel): €\(Int(input.targetPurchasePrice))
                \(L10n.includeIncentivesToggle): \(input.includeIncentives ? "✓" : "—") (~€\(Int(input.estimatedPurchaseIncentiveEUR)))
                \(L10n.tripProfileLabel): \(input.tripProfile.title)
                km/year: \(input.dailyKm)
                €/L: \(String(format: "%.2f", input.fuelPrice)) · €/kWh: \(String(format: "%.2f", input.electricityPricePerKWh))
                """
            )

            drawSection(
                L10n.sourcesSectionTitle,
                """
                • \(L10n.sourceCatalogNote)
                • \(L10n.sourcePricesNote)
                • \(ItalianIncentives.transparencyNote)
                """
            )

            // Footer
            cg.setStrokeColor(ink.withAlphaComponent(0.15).cgColor)
            cg.setLineWidth(1)
            cg.move(to: CGPoint(x: 36, y: pageRect.height - 48))
            cg.addLine(to: CGPoint(x: pageRect.width - 36, y: pageRect.height - 48))
            cg.strokePath()

            let footer = "EVforME? · \(ISO8601DateFormatter().string(from: Date()))"
            (footer as NSString).draw(
                at: CGPoint(x: 36, y: pageRect.height - 36),
                withAttributes: [
                    .font: UIFont.systemFont(ofSize: 9, weight: .medium),
                    .foregroundColor: muted,
                ]
            )
        }
    }

    @MainActor
    static func temporaryPDFURL(result: SimulationResult, input: UserInput) throws -> URL {
        let data = makeReportPDF(result: result, input: input)
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("EVforME-report-\(Int(Date().timeIntervalSince1970)).pdf")
        try data.write(to: url, options: .atomic)
        return url
    }
}

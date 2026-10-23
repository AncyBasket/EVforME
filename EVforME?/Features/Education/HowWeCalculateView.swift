//
//  HowWeCalculateView.swift
//  EVforME?
//
//  “Come calcoliamo” — spiega fonti e formule senza numeri hardcodati in UI.
//

import SwiftUI

struct HowWeCalculateView: View {
    let userInput: UserInput

    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    private var model: HowWeCalculateModel {
        HowWeCalculateExplainer.makeModel(userInput: userInput)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Text(L10n.howWeCalculateIntro)
                        .font(Typography.readingIntro)
                        .foregroundStyle(Color.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("how_we_calculate_intro")

                    Text(L10n.howWeCalculateModelEstimatesNote)
                        .font(Typography.readingCaption)
                        .foregroundStyle(Color.secondaryText)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("how_we_calculate_model_estimates")

                    if let source = model.source {
                        vehicleSection(source)
                    }
                    if let target = model.target {
                        vehicleSection(target)
                    }

                    Text(L10n.howWeCalculateBolloHeading)
                        .font(Typography.readingTitle)
                        .foregroundStyle(Color.ink)
                    Text(L10n.howWeCalculateBolloRegionFormat(model.bolloShared.regionTitle))
                        .font(Typography.readingCaption)
                        .foregroundStyle(Color.secondaryText)

                    if let source = model.source {
                        bolloVehicleSection(source, shared: model.bolloShared)
                    }
                    if let target = model.target {
                        bolloVehicleSection(target, shared: model.bolloShared)
                    }

                    pricesSection
                    co2FormulaSection(model.bolloShared)
                }
                .padding(24)
            }
            .background(Color.appScreenBackground.ignoresSafeArea())
            .navigationTitle(L10n.howWeCalculateTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.guidesSheetClose) { dismiss() }
                }
            }
        }
    }

    private func vehicleSection(_ block: HowWeCalculateVehicleBlock) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(block.roleTitle.uppercased())
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.8)
            Text(block.displayName)
                .font(Typography.readingTitle)
                .foregroundStyle(Color.ink)

            Text(L10n.howWeCalculateConsumptionHeading)
                .font(Typography.readingCardTitle)
                .foregroundStyle(Color.ink)
            Text(L10n.howWeCalculateSourceFormat(block.sourceCategory.localizedTitle))
                .font(Typography.readingBody)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("how_we_calculate_source_category")

            if let url = block.sourceURL {
                Button {
                    openURL(url)
                } label: {
                    Text(L10n.howWeCalculateOpenSource)
                        .font(Typography.bodyBold)
                        .foregroundStyle(Color.ink)
                }
                .accessibilityIdentifier("how_we_calculate_source_link")
            }
            Text(L10n.howWeCalculateConfidenceFormat(block.confidence.localizedTitle))
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)

            if block.showsWeightedEnergyNote {
                Text(L10n.phevWeightedEnergyNote)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
                    .accessibilityIdentifier("how_we_calculate_weighted_note")
            }
            if block.showsCO2ToFuelNote {
                Text(L10n.howWeCalculateCO2AppliesToVehicle)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
                    .accessibilityIdentifier("how_we_calculate_co2_note")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .contain)
    }

    private func bolloVehicleSection(
        _ block: HowWeCalculateVehicleBlock,
        shared: HowWeCalculateBolloShared
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("\(block.roleTitle) — \(block.displayName)")
                .font(Typography.readingCardTitle)
                .foregroundStyle(Color.ink)

            ForEach(Array(bolloExplanationLines(for: block, shared: shared).enumerated()), id: \.offset) { _, line in
                Text(line)
                    .font(Typography.readingBody)
                    .foregroundStyle(Color.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if case .thermalRegional(let showsSuperbollo) = block.bolloPath, showsSuperbollo {
                Text(
                    L10n.howWeCalculateBolloSuperbolloFormat(
                        String(format: "%.0f", shared.superbolloThresholdKw),
                        String(format: "%.0f", shared.superbolloEURPerKwAbove)
                    )
                )
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)
                .accessibilityIdentifier("how_we_calculate_bollo_superbollo")
            }

            Text(bolloAmountLine(for: block))
                .font(Typography.readingCaption)
                .foregroundStyle(Color.ink)
                .accessibilityIdentifier("how_we_calculate_bollo_amount")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 4)
    }

    private func bolloExplanationLines(
        for block: HowWeCalculateVehicleBlock,
        shared: HowWeCalculateBolloShared
    ) -> [String] {
        switch block.bolloPath {
        case .evPermanentExempt:
            return [L10n.howWeCalculateBolloPermanentExempt]
        case .evInExemption(let years):
            return [
                L10n.howWeCalculateBolloEVExemptionActiveFormat(years),
                L10n.howWeCalculateBolloEVAfterExemptionFormat(
                    HowWeCalculateExplainer.formatEURPerKw(
                        HowWeCalculateExplainer.evBolloEURPerKw(for: userInput.italianRegion)
                            ?? shared.nationalEVBolloEURPerKw
                    )
                ),
            ]
        case .evQuarterRate(let rate, let years, let usesNational):
            var lines = [
                L10n.howWeCalculateBolloEVFormulaFormat(
                    years,
                    HowWeCalculateExplainer.formatEURPerKw(rate)
                ),
            ]
            if usesNational {
                lines.append(
                    L10n.howWeCalculateBolloNationalEstimateFormat(
                        HowWeCalculateExplainer.formatEURPerKw(shared.nationalEVBolloEURPerKw)
                    )
                )
            }
            return lines
        case .evNotEstimated:
            return [L10n.howWeCalculateBolloNotEstimated]
        case .thermalRegional:
            return [
                L10n.howWeCalculateBolloThermalRegionalFormat(
                    shared.regionTitle,
                    String(format: "%.0f", shared.superbolloThresholdKw)
                ),
            ]
        case .thermalCatalogEstimate:
            return [L10n.howWeCalculateBolloThermalCatalog]
        case .thermalUnknown:
            return [L10n.howWeCalculateBolloThermalUnknown]
        }
    }

    private func bolloAmountLine(for block: HowWeCalculateVehicleBlock) -> String {
        if !block.bolloIsKnown {
            return L10n.howWeCalculateBolloAmountUnknown
        }
        let average = L10n.howWeCalculateBolloAmountFormat(
            HowWeCalculateExplainer.formatEURAmount(block.bolloAverageEUR)
        )
        let thisYear = L10n.howWeCalculateBolloThisYearFormat(
            HowWeCalculateExplainer.formatEURAmount(block.bolloThisYearEUR)
        )
        return "\(average)\n\(thisYear)"
    }

    private var pricesSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.howWeCalculatePricesHeading)
                .font(Typography.readingTitle)
                .foregroundStyle(Color.ink)
            Text(L10n.howWeCalculatePricesBody)
                .font(Typography.readingBody)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func co2FormulaSection(_ shared: HowWeCalculateBolloShared) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.howWeCalculateCO2Heading)
                .font(Typography.readingTitle)
                .foregroundStyle(Color.ink)
            Text(
                L10n.howWeCalculateCO2BodyFormat(
                    HowWeCalculateExplainer.formatEURPerKw(shared.petrolCO2PerL100),
                    HowWeCalculateExplainer.formatEURPerKw(shared.dieselCO2PerL100)
                )
            )
            .font(Typography.readingBody)
            .foregroundStyle(Color.secondaryText)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityIdentifier("how_we_calculate_co2_formula")

            Button {
                openURL(model.eurLexURL)
            } label: {
                Text(L10n.howWeCalculateOpenEurLex)
                    .font(Typography.bodyBold)
                    .foregroundStyle(Color.ink)
            }
            .accessibilityIdentifier("how_we_calculate_eurlex")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    HowWeCalculateView(
        userInput: UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5
        )
    )
}

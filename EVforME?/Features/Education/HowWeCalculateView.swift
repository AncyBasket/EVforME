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

                    if let source = model.source {
                        vehicleSection(source)
                    }
                    if let target = model.target {
                        vehicleSection(target)
                    }

                    bolloSection(model.bollo)
                    pricesSection
                    co2FormulaSection(model.bollo)
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
            if let label = block.sourceLabel, !label.isEmpty {
                Text(L10n.howWeCalculateSourceFormat(label))
                    .font(Typography.readingBody)
                    .foregroundStyle(Color.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text(L10n.howWeCalculateSourceUnknown)
                    .font(Typography.readingBody)
                    .foregroundStyle(Color.secondaryText)
            }
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
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .contain)
    }

    private func bolloSection(_ bollo: HowWeCalculateBolloBlock) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.howWeCalculateBolloHeading)
                .font(Typography.readingTitle)
                .foregroundStyle(Color.ink)
            Text(L10n.howWeCalculateBolloFormula)
                .font(Typography.readingBody)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)

            Text(L10n.howWeCalculateBolloRegionFormat(bollo.regionTitle))
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)

            if bollo.permanentlyExempt {
                Text(L10n.howWeCalculateBolloPermanentExempt)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            } else if let rate = bollo.evEURPerKw {
                Text(
                    L10n.howWeCalculateBolloRateFormat(
                        String(format: "%.2f", rate)
                    )
                )
                .font(Typography.readingBody)
                .foregroundStyle(Color.ink)
                .accessibilityIdentifier("how_we_calculate_bollo_rate")
                if bollo.evExemptionYears != Int.max {
                    Text(L10n.howWeCalculateBolloExemptionFormat(bollo.evExemptionYears))
                        .font(Typography.readingCaption)
                        .foregroundStyle(Color.secondaryText)
                }
            } else {
                Text(L10n.howWeCalculateBolloNotEstimated)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            }

            if bollo.usesNationalEVEstimate {
                Text(
                    L10n.howWeCalculateBolloNationalEstimateFormat(
                        String(format: "%.2f", bollo.nationalEVBolloEURPerKw)
                    )
                )
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)
                .accessibilityIdentifier("how_we_calculate_bollo_national")
            }

            Text(
                L10n.howWeCalculateBolloSuperbolloFormat(
                    String(format: "%.0f", bollo.superbolloThresholdKw),
                    String(format: "%.0f", bollo.superbolloEURPerKwAbove)
                )
            )
            .font(Typography.readingCaption)
            .foregroundStyle(Color.secondaryText)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
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

    private func co2FormulaSection(_ bollo: HowWeCalculateBolloBlock) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.howWeCalculateCO2Heading)
                .font(Typography.readingTitle)
                .foregroundStyle(Color.ink)
            Text(
                L10n.howWeCalculateCO2BodyFormat(
                    String(format: "%.2f", bollo.petrolCO2PerL100),
                    String(format: "%.2f", bollo.dieselCO2PerL100)
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

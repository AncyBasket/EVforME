//
//  CostsComparisonView.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import SwiftUI

struct CostsComparisonView: View {
    let comparison: [YearlyComparison]
    let userInput: UserInput
    let weeklyCharges: Int
    let sourceBreakdown: OperatingCostBreakdown
    let targetBreakdown: OperatingCostBreakdown

    private var sourceVehicle: VehicleCatalogItem? {
        VehicleCatalogService.shared.vehicle(by: userInput.sourceVehicleId)
    }

    private var targetVehicle: VehicleCatalogItem? {
        VehicleCatalogService.shared.vehicle(by: userInput.targetVehicleId)
    }

    private var sourceFuelLPerKm: Double {
        userInput.sourceConsumptionOverrideLPer100Km.map { $0 / 100.0 }
            ?? sourceVehicle?.fuelConsumptionLPerKm
            ?? 0
    }

    private var targetEnergyKWhPerKm: Double {
        userInput.targetEnergyOverrideKWhPer100Km.map { $0 / 100.0 }
            ?? targetVehicle?.resolvedEnergyKWhPerKm
            ?? 0
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            if let source = sourceVehicle, let target = targetVehicle {
                HStack(alignment: .top, spacing: 12) {
                    VehicleHeroImage(vehicle: source, height: 72, cornerRadius: 2, showsLabelsBelow: true)
                    VehicleHeroImage(vehicle: target, height: 72, cornerRadius: 2, showsLabelsBelow: true)
                }
            }

            Text(
                L10n.vehicleComparisonDimensions(
                    sourceVehicle?.dimensionsText ?? L10n.vehicleDimensionsNotSelected,
                    targetVehicle?.dimensionsText ?? L10n.vehicleDimensionsNotSelected
                )
            )
            .font(Typography.readingCaption)
            .foregroundColor(.secondaryText)

            Link(destination: L10n.externalAutomobileDimensionsComparisonURL) {
                HStack(spacing: 6) {
                    Text(L10n.externalDimensionsLinkTitle)
                        .font(Typography.readingCardTitle)
                    Image(systemName: "arrow.up.right")
                        .font(.caption.weight(.semibold))
                }
                .foregroundColor(.ink)
            }
            .accessibilityHint(L10n.externalDimensionsLinkA11yHint)

            VStack(spacing: 0) {
                HStack(alignment: .top, spacing: 6) {
                    Text("")
                        .frame(width: 52, alignment: .leading)
                    comparisonColumnHeader(
                        title: L10n.gasLabel,
                        subtitle: sourceVehicle?.displayName,
                        titleColor: .iceLine
                    )
                    comparisonColumnHeader(
                        title: L10n.evLabel,
                        subtitle: targetVehicle?.displayName,
                        titleColor: .evLine
                    )
                    comparisonColumnHeader(
                        title: L10n.savings,
                        subtitle: nil,
                        titleColor: .accent
                    )
                }
                .padding(.vertical, 12)
                .padding(.horizontal, 8)
                .background(Color.secondaryText.opacity(0.1))
                
                ForEach(comparison, id: \.year) { year in
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(L10n.yearFormat(year.year))
                            .font(Typography.readingBody)
                            .foregroundColor(.primaryText)
                            .frame(width: 52, alignment: .leading)
                        Text("€\(Int(year.gasCost))")
                            .font(Typography.readingBody)
                            .foregroundColor(.iceLine)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)
                            .lineLimit(1)
                            .minimumScaleFactor(0.75)
                        Text("€\(Int(year.evCost))")
                            .font(Typography.readingBody)
                            .foregroundColor(.evLine)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)
                            .lineLimit(1)
                            .minimumScaleFactor(0.75)
                        Text("€\(Int(year.gasCost - year.evCost))")
                            .font(Typography.readingBody)
                            .bold()
                            .foregroundColor(.accent)
                            .frame(maxWidth: .infinity)
                            .multilineTextAlignment(.center)
                            .lineLimit(1)
                            .minimumScaleFactor(0.75)
                    }
                    .padding(.vertical, 10)
                    .padding(.horizontal, 8)
                    .background(year.year % 2 == 0 ? Color.clear : Color.secondaryText.opacity(0.05))
                }
            }
            .overlay(alignment: .top) {
                Rectangle().fill(Color.hairlineBorder).frame(height: 1)
            }
            
            VStack(alignment: .leading, spacing: 16) {
                Text(L10n.calculationExplanation)
                    .font(Typography.readingCardTitle)
                    .foregroundColor(.primaryText)
                
                VStack(alignment: .leading, spacing: 8) {
                    Text(L10n.calculationGasTitle)
                        .font(Typography.readingCardTitle)
                        .foregroundColor(.primaryText)
                    
                    Text(L10n.calculationGasFormula(
                        userInput.dailyKm,
                        sourceFuelLPerKm,
                        userInput.fuelPrice,
                        sourceBreakdown.energy,
                        sourceBreakdown.total
                    ))
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(.secondaryText)
                    .padding(.leading, 8)
                    
                    Text(L10n.calculationOpexBreakdown(
                        sourceBreakdown.energy,
                        sourceBreakdown.maintenance,
                        sourceBreakdown.taxes,
                        sourceBreakdown.insurance,
                        sourceBreakdown.total
                    ))
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
                    .padding(.leading, 8)
                    .padding(.top, 4)
                    
                    if let lastYear = comparison.last {
                        Text(L10n.calculationGasTotal(lastYear.year, Int(lastYear.gasCost)))
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(.secondaryText)
                            .padding(.leading, 8)
                            .padding(.top, 4)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .overlay(alignment: .leading) { Rectangle().fill(Color.iceLine).frame(width: 3) }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text(L10n.calculationEvTitle)
                        .font(Typography.readingCardTitle)
                        .foregroundColor(.primaryText)
                    
                    Text(L10n.calculationEvFormula(
                        userInput.dailyKm,
                        targetEnergyKWhPerKm,
                        userInput.electricityPricePerKWh,
                        targetBreakdown.energy,
                        targetBreakdown.total
                    ))
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(.secondaryText)
                    .padding(.leading, 8)
                    
                    Text(L10n.calculationOpexBreakdown(
                        targetBreakdown.energy,
                        targetBreakdown.maintenance,
                        targetBreakdown.taxes,
                        targetBreakdown.insurance,
                        targetBreakdown.total
                    ))
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
                    .padding(.leading, 8)
                    .padding(.top, 4)
                    
                    if let lastYear = comparison.last {
                        Text(L10n.calculationEvTotal(lastYear.year, Int(lastYear.evCost)))
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(.secondaryText)
                            .padding(.leading, 8)
                            .padding(.top, 4)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .overlay(alignment: .leading) { Rectangle().fill(Color.evLine).frame(width: 3) }
                
                if let lastYear = comparison.last {
                    let totalSavings = Int(lastYear.gasCost - lastYear.evCost)
                    HStack(spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 10)
                                .fill(Color.accent.opacity(0.15))
                                .frame(width: 36, height: 36)
                            Image(systemName: "eurosign.circle.fill")
                                .font(.title3)
                                .foregroundColor(.accent)
                        }
                        Text(L10n.calculationSavings(lastYear.year, totalSavings))
                            .font(Typography.readingCardTitle)
                            .foregroundColor(.accent)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                Text(L10n.calculationChargingNote(weeklyCharges))
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
            }
        }
    }

    private func comparisonColumnHeader(title: String, subtitle: String?, titleColor: Color) -> some View {
        VStack(alignment: .center, spacing: 4) {
            Text(title)
                .font(Typography.readingCaption)
                .foregroundColor(titleColor)
                .lineLimit(1)
            if let subtitle, !subtitle.isEmpty {
                Text(subtitle)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.78)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

#Preview {
    CostsComparisonView(
        comparison: [
            YearlyComparison(year: 1, gasCost: 4500, evCost: 1800),
            YearlyComparison(year: 2, gasCost: 9000, evCost: 3600),
            YearlyComparison(year: 3, gasCost: 13500, evCost: 5400),
            YearlyComparison(year: 4, gasCost: 18000, evCost: 7200),
            YearlyComparison(year: 5, gasCost: 22500, evCost: 9000)
        ],
        userInput: UserInput(
            dailyKm: 12000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            scenario: .realistic
        ),
        weeklyCharges: 1,
        sourceBreakdown: OperatingCostBreakdown(energy: 3200, maintenance: 700, taxes: 200, insurance: 400),
        targetBreakdown: OperatingCostBreakdown(energy: 900, maintenance: 350, taxes: 0, insurance: 450)
    )
    .padding()
}

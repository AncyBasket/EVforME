//
//  InputView.swift
//  EVforME?
//

import SwiftUI
import PhotosUI
import UIKit

struct InputView: View {

    @Binding var userInput: UserInput
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    /// Se `false`, la vista è incorporata in `MainShellView` (masthead + tab già presenti).
    var useNavigationChrome: Bool = true
    /// Se `false`, non mostrare il poster in cima (evita duplicare il titolo con il masthead).
    var showsTopHero: Bool = true
    var onSimulate: (Scenario) -> Void
    /// Retention 1.1 — azioni sulla card “Ultimo confronto”.
    var onReopenLastComparison: (() -> Void)? = nil
    var onRecalculateLastComparison: (() -> Void)? = nil
    @State private var validationErrors: [String] = []
    @State private var showErrors: Bool = false
    @State private var selectedScenario: Scenario = .realistic
    @State private var appearAnimation: Bool = false
    @State private var sourceVehicles: [VehicleCatalogItem] = []
    @State private var targetVehicles: [VehicleCatalogItem] = []
    @State private var showSourceVehiclePicker = false
    @State private var showTargetVehiclePicker = false
    /// UITEST_OPEN_TARGET_PICKER: open once; never re-open after the tester dismisses the sheet.
    @State private var didAutoOpenTargetPickerForUITest = false
    @State private var stickerItem: PhotosPickerItem?
    @State private var stickerStatus: String?
    @State private var stickerBusy = false
    @State private var history: [SavedScenarioSnapshot] = ScenarioHistoryStore.all()
    @State private var showAdvancedDetails = false
    @State private var lastSnapshot: SavedScenarioSnapshot? = ScenarioHistoryStore.latest()
    @State private var deltaBadgeText: String? = nil

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if showsTopHero {
                    InputScreenHero(appearAnimation: appearAnimation)
                }

                if let snap = lastSnapshot {
                    LastComparisonCard(
                        snapshot: snap,
                        deltaBadge: deltaBadgeText,
                        dataFreshness: dataUpdatedBadgeLabel,
                        onReopen: { onReopenLastComparison?() ?? restoreHistory(snap) },
                        onRecalculate: { onRecalculateLastComparison?() ?? restoreHistory(snap) },
                        onRestoreForm: { restoreFormOnly(snap) }
                    )
                    .padding(.horizontal, 20)
                }

                VStack(alignment: .leading, spacing: 16) {
                // 1) Prima le auto — il resto è opzionale.
                InputSectionCard(
                    step: 1,
                    title: L10n.inputSection3Title,
                    subtitle: L10n.inputQuickVehiclesSubtitle,
                    appearIndex: 1,
                    appearAnimation: appearAnimation
                ) {
                    VehiclePickPairSection(
                        sourceVehicle: selectedSourceVehicle,
                        targetVehicle: selectedTargetVehicle,
                        sourceDimensionsText: selectedSourceVehicle?.dimensionsText ?? L10n.vehicleDimensionsNotSelected,
                        targetDimensionsText: selectedTargetVehicle?.dimensionsText ?? L10n.vehicleDimensionsNotSelected,
                        onSourceTap: { showSourceVehiclePicker = true },
                        onTargetTap: { showTargetVehiclePicker = true }
                    )

                    if let source = selectedSourceVehicle, let target = selectedTargetVehicle {
                        comparisonInset(source: source, target: target)
                    }

                    let thermalP2 = userInput.market == .IT
                        && userInput.italianRegion.hasCitedThermalBolloTariff
                    if selectedSourceVehicle?.powertrain == .ev
                        || (thermalP2 && selectedSourceVehicle.map { $0.powertrain != .ev } == true) {
                        bookletP2Field(
                            label: selectedSourceVehicle?.powertrain == .ev
                                ? L10n.evBookletPowerKwP2SourceLabel
                                : L10n.thermalBookletPowerKwP2SourceLabel,
                            binding: Binding(
                                get: { userInput.sourceBookletPowerKwP2 ?? 0 },
                                set: { userInput.sourceBookletPowerKwP2 = $0 > 0 ? $0 : nil }
                            ),
                            hint: selectedSourceVehicle?.powertrain == .ev
                                ? L10n.evBookletPowerKwP2Hint
                                : L10n.thermalBookletPowerKwP2Hint
                        )
                    }
                    if selectedTargetVehicle?.powertrain == .ev
                        || (thermalP2 && selectedTargetVehicle.map { $0.powertrain != .ev } == true) {
                        bookletP2Field(
                            label: selectedTargetVehicle?.powertrain == .ev
                                ? L10n.evBookletPowerKwP2TargetLabel
                                : L10n.thermalBookletPowerKwP2TargetLabel,
                            binding: Binding(
                                get: { userInput.targetBookletPowerKwP2 ?? 0 },
                                set: { userInput.targetBookletPowerKwP2 = $0 > 0 ? $0 : nil }
                            ),
                            hint: selectedTargetVehicle?.powertrain == .ev
                                ? L10n.evBookletPowerKwP2Hint
                                : L10n.thermalBookletPowerKwP2Hint
                        )
                    }
                    if userInput.market == .IT {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(L10n.italianRegionLabel)
                                .font(Typography.readingCaption)
                                .foregroundStyle(Color.secondaryText)
                            Picker(L10n.italianRegionLabel, selection: $userInput.italianRegion) {
                                ForEach(ItalianRegion.allCases) { region in
                                    Text(region.title).tag(region)
                                }
                            }
                            .pickerStyle(.menu)
                            Text(L10n.italianRegionHint)
                                .font(Typography.readingCaption)
                                .foregroundStyle(Color.secondaryText)
                            if let rateNote = userInput.italianRegion.bolloPickerNote {
                                Text(rateNote)
                                    .font(Typography.readingCaption)
                                    .foregroundStyle(Color.secondaryText)
                                    .accessibilityIdentifier("italian_region_bollo_rate_note")
                            }
                        }
                        .padding(.top, 4)
                    }
                }

                // Sempre visibile (non nel disclosure): senza i campi mancanti non si calcola il verdetto.
                if let incompleteCard = incompleteCatalogPrompt {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(L10n.incompleteCatalogDataTitle)
                            .font(Typography.readingCardTitle)
                            .foregroundColor(.primaryText)
                            .accessibilityIdentifier("incomplete_catalog_data_title")
                        Text(incompleteCard.body)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)
                        ForEach(incompleteCard.officialRows, id: \.key) { row in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(row.label)
                                        .font(Typography.readingCaption)
                                    Spacer()
                                    TextField(
                                        row.placeholder,
                                        value: incompleteOfficialBinding(
                                            key: row.key,
                                            isTarget: incompleteCard.isTarget,
                                            catalogValuePer100: row.valuePer100
                                        ),
                                        format: .number.precision(.fractionLength(0...2))
                                    )
                                    .keyboardType(.decimalPad)
                                    .multilineTextAlignment(.trailing)
                                    .frame(width: 88)
                                    .accessibilityIdentifier("incomplete_catalog_official_\(row.key)")
                                }
                                if let src = row.source, !src.isEmpty {
                                    Text(src)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                        if incompleteCard.needsFuel {
                            HStack {
                                Text(L10n.incompleteCatalogFuelField)
                                    .font(Typography.readingCaption)
                                Spacer()
                                TextField(
                                    "6.5",
                                    value: incompleteFuelBinding(forTarget: incompleteCard.isTarget),
                                    format: .number.precision(.fractionLength(1...2))
                                )
                                .keyboardType(.decimalPad)
                                .multilineTextAlignment(.trailing)
                                .frame(width: 88)
                                .accessibilityIdentifier("incomplete_catalog_fuel_field")
                            }
                        }
                        if incompleteCard.needsEnergy {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(L10n.incompleteCatalogEnergyField)
                                        .font(Typography.readingCaption)
                                    Spacer()
                                    TextField(
                                        "18",
                                        value: incompleteEnergyBinding(forTarget: incompleteCard.isTarget),
                                        format: .number.precision(.fractionLength(1...2))
                                    )
                                    .keyboardType(.decimalPad)
                                    .multilineTextAlignment(.trailing)
                                    .frame(width: 88)
                                    .accessibilityIdentifier("incomplete_catalog_energy_field")
                                }
                                if incompleteCard.showWeightedEnergyHonesty {
                                    Text(L10n.incompleteCatalogWeightedEnergyHonesty)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                        .fixedSize(horizontal: false, vertical: true)
                                        .accessibilityIdentifier("incomplete_catalog_weighted_honesty")
                                }
                            }
                        }
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.primaryText.opacity(0.06))
                    .accessibilityElement(children: .contain)
                    .accessibilityIdentifier("incomplete_catalog_data_card")
                }

                DisclosureGroup(isExpanded: $showAdvancedDetails) {
                    VStack(alignment: .leading, spacing: 22) {
                        InputSectionCard(
                            step: 2,
                            title: L10n.inputSection1Title,
                            subtitle: L10n.inputSection1Subtitle,
                            appearIndex: 2,
                            appearAnimation: appearAnimation
                        ) {
                            sliderBlock(
                                title: L10n.dailyKmQuestion,
                                valueLabel: L10n.yearlyKmValue(userInput.dailyKm),
                                accessibilityLabel: L10n.yearlyKmSliderA11y,
                                accessibilityValue: L10n.yearlyKmValue(userInput.dailyKm)
                            ) {
                                Slider(
                                    value: Binding(
                                        get: { Double(userInput.dailyKm) },
                                        set: { newValue in
                                            let old = userInput.dailyKm
                                            userInput.dailyKm = Int(newValue)
                                            if userInput.tripProfile != .custom {
                                                userInput.tripProfile = .custom
                                            }
                                            if Int(newValue) % 5000 == 0, Int(newValue) != old {
                                                UISelectionFeedbackGenerator().selectionChanged()
                                            }
                                        }
                                    ),
                                    in: 1000...120_000,
                                    step: 500
                                )
                                .tint(.accent)
                                .accessibilityIdentifier("yearly_km_slider")
                            }

                            sliderBlock(
                                title: fuelPriceSliderTitle,
                                valueLabel: fuelPriceValueLabel,
                                accessibilityLabel: L10n.fuelPriceSliderA11y,
                                accessibilityValue: fuelPriceA11yValue
                            ) {
                                Slider(
                                    value: Binding(
                                        get: { userInput.fuelPrice },
                                        set: { newValue in
                                            userInput.fuelPrice = newValue
                                            if Int(newValue * 20) % 5 == 0 {
                                                UISelectionFeedbackGenerator().selectionChanged()
                                            }
                                        }
                                    ),
                                    in: fuelPriceSliderRange,
                                    step: fuelPriceSliderStep
                                )
                                .tint(.accent)
                                .accessibilityIdentifier("fuel_price_slider")
                            }

                            sliderBlock(
                                title: L10n.electricityPriceLabel,
                                valueLabel: String(format: "€%.2f/kWh", userInput.electricityPricePerKWh),
                                accessibilityLabel: L10n.electricityPriceSliderA11y,
                                accessibilityValue: L10n.electricityPriceA11yValue(userInput.electricityPricePerKWh)
                            ) {
                                Slider(
                                    value: Binding(
                                        get: { userInput.electricityPricePerKWh },
                                        set: { newValue in
                                            userInput.electricityPricePerKWh = newValue
                                            if Int(newValue * 100) % 5 == 0 {
                                                UISelectionFeedbackGenerator().selectionChanged()
                                            }
                                        }
                                    ),
                                    in: 0.05...2.0,
                                    step: 0.01
                                )
                                .tint(.accent)
                            }

                            Text(pricesFreshnessLabel)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .padding(.top, 4)

                            VStack(alignment: .leading, spacing: 10) {
                                Text(L10n.ownershipYearsLabel)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                HStack {
                                    Text("\(userInput.ownershipYears)")
                                        .font(Typography.metric)
                                        .foregroundColor(.primaryText)
                                        .frame(minWidth: 36, alignment: .leading)
                                    Text(userInput.ownershipYears == 1 ? L10n.yearSingular : L10n.yearPlural)
                                        .font(Typography.readingBody)
                                        .foregroundColor(.secondaryText)
                                    Spacer()
                                    Stepper(
                                        "",
                                        value: Binding(
                                            get: { userInput.ownershipYears },
                                            set: { newValue in
                                                userInput.ownershipYears = newValue
                                                UISelectionFeedbackGenerator().selectionChanged()
                                            }
                                        ),
                                        in: 1...20
                                    )
                                    .labelsHidden()
                                    .tint(.accent)
                                }
                            }

                            Text(L10n.areaTypeLabel)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .padding(.top, 8)
                            VStack(alignment: .leading, spacing: 6) {
                                Text(L10n.marketPickerLabel)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(Color.secondaryText)
                                Picker(L10n.marketPickerLabel, selection: $userInput.market) {
                                    ForEach(AppMarket.pickerCases) { market in
                                        Text(market.localizedName).tag(market)
                                    }
                                }
                                .pickerStyle(.menu)
                                Text(L10n.marketMaintenanceSource(userInput.market))
                                    .font(.caption)
                                    .foregroundStyle(Color.secondaryText)
                                    .fixedSize(horizontal: false, vertical: true)
                                if userInput.market != .IT {
                                    Text(L10n.nonItalyDataHonestyBanner)
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(Color.ink)
                                        .fixedSize(horizontal: false, vertical: true)
                                        .padding(10)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(Color.surfaceElevated.opacity(0.95))
                                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                }
                            }

                            Picker(L10n.areaTypeLabel, selection: $userInput.areaType) {
                                ForEach(AreaType.allCases) { areaType in
                                    Text(areaType.title).tag(areaType)
                                }
                            }
                            .pickerStyle(.segmented)
                            .onChange(of: userInput.areaType) { _, _ in
                                if userInput.tripProfile != .custom {
                                    userInput.tripProfile = .custom
                                }
                            }

                            Text(L10n.tripProfileLabel)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .padding(.top, 10)
                            Picker(L10n.tripProfileLabel, selection: $userInput.tripProfile) {
                                ForEach(TripProfile.allCases) { profile in
                                    Text(profile.title).tag(profile)
                                }
                            }
                            .pickerStyle(.segmented)
                            .onChange(of: userInput.tripProfile) { _, profile in
                                if profile != .custom {
                                    userInput.applyTripProfileDefaults()
                                }
                            }
                            Text(L10n.assumptionModelEstimatesNote)
                                .font(Typography.caption)
                                .foregroundStyle(Color.secondaryText)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.top, 6)
                        }

                        InputSectionCard(
                            step: 3,
                            title: L10n.inputSection4Title,
                            subtitle: L10n.inputSection4Subtitle,
                            appearIndex: 3,
                            appearAnimation: appearAnimation
                        ) {
                            Toggle(L10n.homeChargingToggle, isOn: $userInput.hasHomeCharging)
                                .font(Typography.readingBody)
                                .tint(.accent)
                                .padding(.vertical, 4)
                                .onChange(of: userInput.hasHomeCharging) { _, _ in
                                    userInput.chargingConfiguration = userInput.resolvedChargingConfiguration()
                                }
                                .onChange(of: userInput.dailyKm) { _, _ in
                                    userInput.chargingConfiguration = userInput.resolvedChargingConfiguration()
                                }
                                .onChange(of: userInput.electricityPricePerKWh) { _, _ in
                                    userInput.chargingConfiguration.customHomePricePerKWh = userInput.electricityPricePerKWh
                                }

                            Text(L10n.publicChargingTypeLabel)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .padding(.top, 8)
                            Picker(L10n.publicChargingTypeLabel, selection: $userInput.chargingConfiguration.publicChargingType) {
                                ForEach(ChargingType.publicCases(targetBrandIsTesla: targetBrandIsTesla)) { type in
                                    Text(type.displayName).tag(type)
                                }
                            }
                            .pickerStyle(.menu)
                            .onChange(of: userInput.targetVehicleId) { _, _ in
                                let allowed = ChargingType.publicCases(targetBrandIsTesla: targetBrandIsTesla)
                                if !allowed.contains(userInput.chargingConfiguration.publicChargingType) {
                                    userInput.chargingConfiguration.publicChargingType = .publicFast
                                }
                            }
                            Text(L10n.publicChargingSourceNote)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)

                            if let period = OfficialCostService.shared.cachedOrBundledCosts()?.electricityPeriod {
                                Text(L10n.electricityEurostatPeriod(period))
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                            }

                            Text(L10n.insuranceAnnualOptionalLabel)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .padding(.top, 10)
                            TextField(
                                L10n.insuranceAnnualOptionalPlaceholder,
                                value: Binding(
                                    get: { userInput.annualInsuranceOverrideEUR ?? 0 },
                                    set: { userInput.annualInsuranceOverrideEUR = $0 > 0 ? $0 : nil }
                                ),
                                format: .number
                            )
                            .keyboardType(.decimalPad)
                            .font(Typography.readingBody)
                            Toggle(L10n.kaskoTheftToggle, isOn: $userInput.includeKaskoTheft)
                                .font(Typography.readingBody)
                                .tint(.accent)
                            if userInput.includeKaskoTheft {
                                Text(L10n.kaskoTheftAmountLabel)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                TextField(
                                    L10n.kaskoTheftAmountPlaceholder,
                                    value: Binding(
                                        get: { userInput.annualKaskoEUR ?? 0 },
                                        set: { userInput.annualKaskoEUR = $0 > 0 ? $0 : nil }
                                    ),
                                    format: .number
                                )
                                .keyboardType(.decimalPad)
                                .font(Typography.readingBody)
                            }

                            VStack(alignment: .leading, spacing: 10) {
                                Text(L10n.comparisonIntentSectionTitle)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                Picker(L10n.comparisonIntentSectionTitle, selection: $userInput.comparisonIntent) {
                                    ForEach(ComparisonIntent.allCases) { intent in
                                        Text(intent.title).tag(intent)
                                    }
                                }
                                .pickerStyle(.segmented)
                                Text(userInput.comparisonIntent.subtitle)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                    .fixedSize(horizontal: false, vertical: true)

                                // Listino solo come extra “se compro”: non entra nel sì/no.
                                if userInput.comparisonIntent == .consideringPurchase {
                                    Text(L10n.purchasePricesTitle)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                        .padding(.top, 4)
                                    Text(L10n.purchasePricesVerdictNote)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                        .fixedSize(horizontal: false, vertical: true)
                                    HStack {
                                        Text(L10n.sourcePurchasePriceLabel)
                                            .font(Typography.readingCaption)
                                        Spacer()
                                        TextField("12000", value: $userInput.sourcePurchasePrice, format: .number)
                                            .keyboardType(.decimalPad)
                                            .multilineTextAlignment(.trailing)
                                            .frame(width: 100)
                                    }
                                    HStack {
                                        Text(L10n.targetPurchasePriceLabel)
                                            .font(Typography.readingCaption)
                                        Spacer()
                                        TextField("32000", value: $userInput.targetPurchasePrice, format: .number)
                                            .keyboardType(.decimalPad)
                                            .multilineTextAlignment(.trailing)
                                            .frame(width: 100)
                                    }
                                    if userInput.showsItalyCostKit {
                                        Toggle(L10n.includeIncentivesToggle, isOn: $userInput.includeIncentives)
                                            .font(Typography.readingBody)
                                            .tint(.accent)
                                        Text(L10n.includeIncentivesHint)
                                            .font(Typography.readingCaption)
                                            .foregroundColor(.secondaryText)
                                    }
                                }
                            }
                            .padding(.top, 8)

                            VStack(alignment: .leading, spacing: 8) {
                                Text(L10n.stickerScanTitle)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                PhotosPicker(selection: $stickerItem, matching: .images) {
                                    Label(L10n.stickerScanButton, systemImage: "doc.viewfinder")
                                        .font(Typography.readingCardTitle)
                                }
                                .onChange(of: stickerItem) { _, item in
                                    Task { await runStickerOCR(item) }
                                }
                                if stickerBusy {
                                    ProgressView()
                                } else if let stickerStatus {
                                    Text(stickerStatus)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                }
                                if userInput.sourceConsumptionOverrideLPer100Km != nil
                                    || userInput.targetEnergyOverrideKWhPer100Km != nil
                                    || userInput.sourceEnergyOverrideKWhPer100Km != nil
                                    || userInput.targetFuelConsumptionOverrideLPer100Km != nil {
                                    Button(L10n.stickerClearOverride) {
                                        userInput.sourceConsumptionOverrideLPer100Km = nil
                                        userInput.targetEnergyOverrideKWhPer100Km = nil
                                        userInput.sourceEnergyOverrideKWhPer100Km = nil
                                        userInput.targetFuelConsumptionOverrideLPer100Km = nil
                                        stickerStatus = nil
                                        stickerItem = nil
                                    }
                                    .font(Typography.readingCaption)
                                }
                                Text(L10n.stickerScanHint)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                            }
                            .padding(.top, 10)

                            VStack(alignment: .leading, spacing: 10) {
                                Text(L10n.scenarioTitle)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                scenarioChips
                                Text(selectedScenario.scenarioDescription)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .padding(.top, 6)

                            if !history.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(L10n.historySectionTitle)
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                    ForEach(history.prefix(4)) { item in
                                        Button {
                                            restoreHistory(item)
                                        } label: {
                                            HStack {
                                                VStack(alignment: .leading, spacing: 2) {
                                                    Text(item.verdictTitle)
                                                        .font(Typography.readingCardTitle)
                                                        .foregroundColor(.primaryText)
                                                    Text("\(item.yearlyKm) km · €\(item.savingsMin)–€\(item.savingsMax)")
                                                        .font(Typography.readingCaption)
                                                        .foregroundColor(.secondaryText)
                                                    if item.showsPartialBolloTotal {
                                                        Text(L10n.partialTotalBolloUnknown)
                                                            .font(Typography.readingCaption)
                                                            .foregroundColor(.warning)
                                                    }
                                                }
                                                Spacer()
                                                Image(systemName: "arrow.uturn.backward.circle.fill")
                                                    .foregroundStyle(Color.accent)
                                            }
                                            .padding(.vertical, 6)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .padding(.top, 8)
                            }
                        }
                    }
                    .padding(.top, 12)
                } label: {
                    Text(L10n.inputAdvancedDetailsTitle)
                        .font(Typography.readingCardTitle)
                        .foregroundColor(.primaryText)
                }
                .tint(.accent)
                .padding(.horizontal, 4)

                if showErrors && !validationErrors.isEmpty {
                    errorBanner
                        .transition(errorBannerTransition)
                }

                Color.clear.frame(height: 28)
                }
                .padding(.horizontal, 20)
            }
            .padding(.top, 8)
        }
        .scrollIndicators(.hidden)
        .scrollDismissesKeyboard(.interactively)
        .background(screenBackground)
        .animation(
            accessibilityReduceMotion ? .easeOut(duration: 0.16) : .spring(response: 0.4, dampingFraction: 0.84),
            value: showErrors && !validationErrors.isEmpty
        )
        .safeAreaInset(edge: .bottom, spacing: 0) { bottomActionBar }
        .modifier(InputNavigationChromeModifier(enabled: useNavigationChrome))
        .onAppear {
            selectedScenario = userInput.scenario
            refreshHistoryState()
            loadCatalog()
#if DEBUG
            if ProcessInfo.processInfo.environment["UITEST_EXPAND_ADVANCED"] == "1"
                || ProcessInfo.processInfo.environment["UITEST_INCOMPLETE_PHEV"] == "1"
                || ProcessInfo.processInfo.environment["UITEST_PARTIAL_PHEV_KWH_ONLY"] == "1" {
                showAdvancedDetails = true
            }
            if ProcessInfo.processInfo.environment["UITEST_PARTIAL_PHEV_KWH_ONLY"] == "1" {
                userInput.targetVehicleId = "bmw-x1-phev-xdrive25e-2024"
            } else if ProcessInfo.processInfo.environment["UITEST_INCOMPLETE_PHEV"] == "1" {
                userInput.targetVehicleId = "jeep-compass-phev-4xe-2022"
            }
            if ProcessInfo.processInfo.environment["UITEST_OPEN_TARGET_PICKER"] == "1",
               !didAutoOpenTargetPickerForUITest {
                didAutoOpenTargetPickerForUITest = true
                showTargetVehiclePicker = true
            }
            // UI test: ripristina prezzo forzato anche senza onChange del veicolo.
            if let raw = ProcessInfo.processInfo.environment["UITEST_FUEL_PRICE"],
               let price = Double(raw.replacingOccurrences(of: ",", with: ".")) {
                userInput.fuelPrice = price
            }
#endif
            if accessibilityReduceMotion {
                appearAnimation = true
            } else {
                withAnimation(.spring(response: 0.48, dampingFraction: 0.86)) {
                    appearAnimation = true
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .evVehicleCatalogDidUpdate)) { _ in
            loadCatalog()
        }
        .onReceive(NotificationCenter.default.publisher(for: .evScenarioHistoryDidChange)) { _ in
            refreshHistoryState()
        }
        .onReceive(NotificationCenter.default.publisher(for: .catalogVehicleSelectionRequested)) { _ in
            showTargetVehiclePicker = true
        }
        .task {
            await VehicleCatalogService.shared.refreshFromRemoteIfPossible()
            loadCatalog()
#if DEBUG
            // Only the first auto-open; a late refresh must not re-cover the bench CTA.
            if ProcessInfo.processInfo.environment["UITEST_OPEN_TARGET_PICKER"] == "1",
               !didAutoOpenTargetPickerForUITest {
                didAutoOpenTargetPickerForUITest = true
                try? await Task.sleep(nanoseconds: 600_000_000)
                showTargetVehiclePicker = true
            }
#endif
        }
        .sheet(isPresented: $showSourceVehiclePicker) {
            VehicleCatalogPickerSheet(
                title: L10n.sourceVehicleLabel,
                vehicles: sourceVehicles,
                selectedId: $userInput.sourceVehicleId
            )
        }
        .sheet(isPresented: $showTargetVehiclePicker) {
            VehicleCatalogPickerSheet(
                title: L10n.targetVehicleLabel,
                vehicles: targetVehicles,
                selectedId: $userInput.targetVehicleId
            )
        }
        .onChange(of: userInput.sourceVehicleId) { _, newId in
            guard let vehicle = sourceVehicles.first(where: { $0.id == newId }) else { return }
            userInput.sourcePurchasePrice = Defaults.suggestedPurchasePrice(for: vehicle)
            applySuggestedComparisonIntent()
            _ = StorageService.shared.syncFuelPriceForSourceVehicle(in: &userInput)
            // UI test: ripristina prezzo forzato dopo sync ufficiale.
            if let raw = ProcessInfo.processInfo.environment["UITEST_FUEL_PRICE"],
               let price = Double(raw.replacingOccurrences(of: ",", with: ".")) {
                userInput.fuelPrice = price
            }
        }
        .onChange(of: userInput.targetVehicleId) { _, newId in
            guard let vehicle = targetVehicles.first(where: { $0.id == newId })
                    ?? VehicleCatalogService.shared.vehicle(by: newId) else { return }
            userInput.targetPurchasePrice = Defaults.suggestedPurchasePrice(for: vehicle)
            applySuggestedComparisonIntent()
        }
        .onChange(of: showTargetVehiclePicker) { _, isShowing in
#if DEBUG
            // After the forced UITEST picker dismisses on a version pick, open verdict
            // without relying on a hittable bottom CTA under modal/safe-area flakes.
            guard !isShowing,
                  ProcessInfo.processInfo.environment["UITEST_OPEN_TARGET_PICKER"] == "1" else { return }
            let id = userInput.targetVehicleId
            let picked = targetVehicles.first(where: { $0.id == id })
                ?? VehicleCatalogService.shared.vehicle(by: id)
            guard let picked, picked.isEEAVariantChild || id.contains("-v") else { return }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 550_000_000)
                validateAndSimulate()
            }
#endif
        }
    }

    private func applySuggestedComparisonIntent() {
        guard let source = selectedSourceVehicle, let target = selectedTargetVehicle else { return }
        userInput.comparisonIntent = ComparisonIntent.suggested(
            sourceYear: source.year,
            targetYear: target.year
        )
    }

    private var pricesFreshnessLabel: String {
        guard let date = OfficialCostService.shared.lastSuccessfulFetchDate else {
            return L10n.pricesFreshBundled
        }
        let minutes = Int(Date().timeIntervalSince(date) / 60)
        if minutes < 2 {
            return L10n.pricesFreshJustNow
        }
        if minutes < 24 * 60 {
            return L10n.pricesFreshMinutesAgo(minutes)
        }
        return L10n.pricesFreshCached
    }

    private var dataUpdatedBadgeLabel: String {
        let energyDate = OfficialCostService.shared.lastSuccessfulFetchDate
        let incentivesDate = ItalianIncentivesService.shared.lastSuccessfulFetchDate
        let best = [energyDate, incentivesDate].compactMap { $0 }.max()
        guard let best else {
            return L10n.dataUpdatedBadgeBundled
        }
        let formatter = DateFormatter()
        formatter.locale = .current
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return L10n.dataUpdatedBadgeAt(formatter.string(from: best))
    }

    private func refreshHistoryState() {
        history = ScenarioHistoryStore.all()
        lastSnapshot = ScenarioHistoryStore.latest()
        deltaBadgeText = makeDeltaBadge(for: lastSnapshot)
    }

    private func makeDeltaBadge(for snapshot: SavedScenarioSnapshot?) -> String? {
        guard let snapshot else { return nil }
        if snapshot.hasUnavailableCatalogVehicle {
            return L10n.catalogVehiclePickAnother
        }
        var input = snapshot.restoredUserInput()
        let fuelKind = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.resolvedFuelKind ?? .petrol
        let liveFuel = ScenarioLiveDelta.liveFuelPrice(fallback: input.fuelPrice, fuelKind: fuelKind)
        let liveElec = ScenarioLiveDelta.liveElectricityPrice(fallback: input.electricityPricePerKWh)
        input.fuelPrice = liveFuel
        input.electricityPricePerKWh = liveElec
        let liveResult = EVSimulator.simulate(input: input)
        let report = ScenarioLiveDelta.evaluate(
            snapshot: snapshot,
            liveFuel: liveFuel,
            liveElectricity: liveElec,
            liveIncentiveEUR: input.estimatedPurchaseIncentiveEUR,
            liveResult: liveResult
        )
        // La card mostra già `windowBadgeText` quando non c’è delta: qui solo variazioni prezzi/risparmio.
        if report.isMaterial, let min = report.currentSavingsMin, let max = report.currentSavingsMax {
            return max > 0
                ? L10n.lastComparisonDataChanged(min, max)
                : L10n.lastComparisonDataChangedCheaper
        }
        if snapshot.fuelPriceAtSave != nil || snapshot.electricityPriceAtSave != nil {
            return L10n.lastComparisonDataUnchanged
        }
        return nil
    }

    private func restoreFormOnly(_ item: SavedScenarioSnapshot) {
        if item.hasUnavailableCatalogVehicle {
            stickerStatus = L10n.catalogVehiclePickAnother
            ErrorHandler.shared.handleAppError(
                .dataNotFound,
                context: .catalog,
                userMessage: L10n.catalogVehiclePickAnother
            )
            UISelectionFeedbackGenerator().selectionChanged()
            return
        }
        let restored = item.restoredUserInput()
        guard CatalogVehicleIdResolver.hasResolvableVehiclePair(restored) else {
            stickerStatus = L10n.catalogVehiclePickAnother
            ErrorHandler.shared.handleAppError(
                .dataNotFound,
                context: .catalog,
                userMessage: L10n.catalogVehiclePickAnother
            )
            UISelectionFeedbackGenerator().selectionChanged()
            return
        }
        userInput = restored
        selectedScenario = restored.scenario
        UISelectionFeedbackGenerator().selectionChanged()
    }

    private func runStickerOCR(_ item: PhotosPickerItem?) async {
        guard let item else { return }
        stickerBusy = true
        defer { stickerBusy = false }
        guard let data = try? await item.loadTransferable(type: Data.self),
              let image = UIImage(data: data) else {
            stickerStatus = L10n.stickerScanNothing
            return
        }
        let result = await StickerOCRService.recognize(from: image)
        if let fuel = result.fuelLPer100Km {
            userInput.sourceConsumptionOverrideLPer100Km = fuel
            stickerStatus = String(format: L10n.string("sticker_scan_found_fuel"), fuel)
        } else if let energy = result.energyKWhPer100Km {
            userInput.targetEnergyOverrideKWhPer100Km = energy
            stickerStatus = String(format: L10n.string("sticker_scan_found_energy"), energy)
        } else {
            stickerStatus = L10n.stickerScanNothing
        }
    }

    private func restoreHistory(_ item: SavedScenarioSnapshot) {
        if item.hasUnavailableCatalogVehicle {
            stickerStatus = L10n.catalogVehiclePickAnother
            ErrorHandler.shared.handleAppError(
                .dataNotFound,
                context: .catalog,
                userMessage: L10n.catalogVehiclePickAnother
            )
            UISelectionFeedbackGenerator().selectionChanged()
            return
        }
        let restored = item.restoredUserInput()
        guard CatalogVehicleIdResolver.hasResolvableVehiclePair(restored) else {
            stickerStatus = L10n.catalogVehiclePickAnother
            ErrorHandler.shared.handleAppError(
                .dataNotFound,
                context: .catalog,
                userMessage: L10n.catalogVehiclePickAnother
            )
            UISelectionFeedbackGenerator().selectionChanged()
            return
        }
        userInput = restored
        selectedScenario = restored.scenario
        UISelectionFeedbackGenerator().selectionChanged()
        onSimulate(restored.scenario)
    }

    private var errorBannerTransition: AnyTransition {
        if accessibilityReduceMotion {
            return .opacity
        }
        return .move(edge: .bottom).combined(with: .opacity)
    }

    private var screenBackground: some View {
        Group {
            if useNavigationChrome {
                ImmersiveBackground()
            } else {
                Color.clear
            }
        }
    }

    private var bottomActionBar: some View {
        VStack(spacing: 0) {
            Button(action: validateAndSimulate) {
                HStack(spacing: 10) {
                    Text(L10n.tellMeTheTruth)
                    Image(systemName: "arrow.right")
                        .font(.system(size: 14, weight: .semibold))
                }
                .font(Typography.bodyBold)
                .foregroundStyle(Color.ctaLabel)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
                .background(Color.ctaFill)
                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                .overlay(alignment: .bottom) {
                    Rectangle()
                        .fill(Color.accent)
                        .frame(height: 3)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel(L10n.tellMeTheTruth)
            .accessibilityHint(L10n.simulateCtaA11yHint)
            .padding(.horizontal, 22)
            .padding(.top, 12)
            .padding(.bottom, 10)
        }
        .background(.ultraThinMaterial.opacity(0.92))
        .overlay(
            Rectangle()
                .fill(Color.hairlineBorder)
                .frame(height: 1),
            alignment: .top
        )
    }

    private var scenarioChips: some View {
        HStack(spacing: 8) {
            ForEach(Scenario.allCases) { scenario in
                let selected = selectedScenario == scenario
                Button {
                    let anim: Animation = accessibilityReduceMotion
                        ? .easeOut(duration: 0.18)
                        : .spring(response: 0.35, dampingFraction: 0.78)
                    withAnimation(anim) {
                        selectedScenario = scenario
                        userInput.scenario = scenario
                    }
                    UISelectionFeedbackGenerator().selectionChanged()
                } label: {
                    Text(scenario.title)
                        .font(Typography.readingCaption)
                        .fontWeight(.semibold)
                        .padding(.vertical, 10)
                        .padding(.horizontal, 12)
                        .frame(maxWidth: .infinity)
                        .background(
                            RoundedRectangle(cornerRadius: 2, style: .continuous)
                                .fill(selected ? Color.ctaFill : Color.clear)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 2, style: .continuous)
                                .stroke(Color.ink.opacity(selected ? 0 : 0.25), lineWidth: 1)
                        )
                        .foregroundColor(selected ? Color.ctaLabel : Color.ink)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(scenario.title)
                .accessibilityHint(L10n.scenarioChipA11yHint)
                .accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
    }

    private var errorBanner: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(validationErrors, id: \.self) { error in
                Text(error)
                    .font(Typography.readingBody)
                    .foregroundColor(.ink)
            }
        }
        .padding(.vertical, 12)
        .padding(.leading, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(Color.warning)
                .frame(width: 3)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(validationErrorsA11yLabel)
        .accessibilityAddTraits(.isHeader)
    }

    private var validationErrorsA11yLabel: String {
        L10n.validationA11yTitle + ": " + validationErrors.joined(separator: "; ")
    }

    private func bookletP2Field(label: String, binding: Binding<Double>, hint: String = L10n.evBookletPowerKwP2Hint) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.top, 8)
            TextField(L10n.evBookletPowerKwP2Placeholder, value: binding, format: .number)
                .keyboardType(.decimalPad)
                .font(Typography.readingBody)
            Text(hint)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
        }
    }

    @ViewBuilder
    private func sliderBlock<Controls: View>(
        title: String,
        valueLabel: String,
        accessibilityLabel: String,
        accessibilityValue: String,
        @ViewBuilder controls: () -> Controls
    ) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
            controls()
                .accessibilityLabel(accessibilityLabel)
                .accessibilityValue(accessibilityValue)
            Text(valueLabel)
                .font(Typography.metric)
                .foregroundColor(.primaryText)
        }
    }

    private func comparisonInset(source: VehicleCatalogItem, target: VehicleCatalogItem) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.comparisonCardTitle.uppercased())
                .font(Typography.sectionEyebrow)
                .foregroundColor(.secondaryText)
                .tracking(0.8)

            Text(L10n.vehicleComparisonDimensions(source.dimensionsText, target.dimensionsText))
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)

            // Gestione al km senza costo di acquisto: energia + bollo + manut. (età).
            // L’usata pesa di più in manutenzione; la nuova no via listino qui.
            Text(L10n.comparisonOperatingPerKmCaption)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)

            VStack(spacing: 8) {
                costRow(name: source.displayName, value: operatingCostPerKm(for: source), color: .iceLine)
                costRow(name: target.displayName, value: operatingCostPerKm(for: target), color: .evLine)
            }
            if userInput.dailyKm < 100 {
                Text(L10n.operatingCostEnterKmHint)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
            }
            if source.usesEPACatalogSource || target.usesEPACatalogSource {
                Text(
                    source.usesEPACatalogSource && target.usesEPACatalogSource
                        ? L10n.phevCatalogUsaNote
                        : L10n.phevCatalogEpaVehicleNote
                )
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .accessibilityIdentifier("phev_catalog_usa_note")
            }
            if source.usesWeightedElectricEnergy || target.usesWeightedElectricEnergy {
                Text(L10n.phevWeightedEnergyNote)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
                    .accessibilityIdentifier("phev_weighted_energy_note")
            }
        }
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) {
            Rectangle().fill(Color.hairlineBorder).frame(height: 1)
        }
    }

    private func costRow(name: String, value: Double?, color: Color) -> some View {
        HStack {
            Text(name)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .lineLimit(1)
            Spacer()
            Text(value.map { String(format: "€%.3f/km", $0) } ?? "—")
                .font(Typography.readingCardTitle)
                .foregroundColor(color)
                .monospacedDigit()
        }
    }

    private struct IncompleteOfficialRow: Equatable {
        let key: String
        let label: String
        let placeholder: String
        /// Valore catalogo già in unità UI (L/100 o kWh/100 o km o kWh).
        let valuePer100: Double
        let source: String?
    }

    private struct IncompleteCatalogPrompt {
        let isTarget: Bool
        let body: String
        let needsFuel: Bool
        let needsEnergy: Bool
        let showWeightedEnergyHonesty: Bool
        let officialRows: [IncompleteOfficialRow]
    }

    /// Prefer target if incomplete (usual compare path); else source.
    private var incompleteCatalogPrompt: IncompleteCatalogPrompt? {
        let catalog = VehicleCatalogService.shared
        let target = catalog.vehicle(by: userInput.targetVehicleId)
        let source = catalog.vehicle(by: userInput.sourceVehicleId)
        if let target, target.hasIncompleteCatalogData {
            return prompt(for: target, isTarget: true)
        }
        if let source, source.hasIncompleteCatalogData {
            return prompt(for: source, isTarget: false)
        }
        return nil
    }

    private func prompt(for vehicle: VehicleCatalogItem, isTarget: Bool) -> IncompleteCatalogPrompt {
        switch vehicle.powertrain {
        case .phev:
            let needsFuel = vehicle.usableChargeSustainingFuelLPerKm == nil
            let needsEnergy = vehicle.usableChargeDepletingEnergyKWhPerKm == nil
            let onlyEnergy = needsEnergy && !needsFuel
            let body = onlyEnergy
                ? L10n.incompleteCatalogDataBodyPHEVEnergyOnly
                : L10n.incompleteCatalogDataBodyPHEV
            var official: [IncompleteOfficialRow] = []
            if let cs = vehicle.usableChargeSustainingFuelLPerKm {
                official.append(
                    IncompleteOfficialRow(
                        key: "fuelConsumptionLPerKm",
                        label: L10n.incompleteCatalogFuelField,
                        placeholder: "6.5",
                        valuePer100: cs * 100.0,
                        source: vehicle.fieldSource(for: "fuelConsumptionLPerKm")
                    )
                )
            }
            if let range = vehicle.wltpRangeKm {
                official.append(
                    IncompleteOfficialRow(
                        key: "wltpRangeKm",
                        label: L10n.incompleteCatalogRangeField,
                        placeholder: "60",
                        valuePer100: Double(range),
                        source: vehicle.fieldSource(for: "wltpRangeKm")
                    )
                )
            }
            if let bat = vehicle.batteryKWh {
                official.append(
                    IncompleteOfficialRow(
                        key: "batteryKWh",
                        label: L10n.incompleteCatalogBatteryField,
                        placeholder: "14",
                        valuePer100: bat,
                        source: vehicle.fieldSource(for: "batteryKWh")
                    )
                )
            }
            let honesty = needsEnergy && (
                vehicle.weightedEnergyConsumptionKWhPerKm != nil
                    || (vehicle.sourceName ?? "").localizedCaseInsensitiveContains("gewichtet")
                    || (vehicle.sourceName ?? "").localizedCaseInsensitiveContains("ponderat")
            )
            return IncompleteCatalogPrompt(
                isTarget: isTarget,
                body: body,
                needsFuel: needsFuel,
                needsEnergy: needsEnergy,
                showWeightedEnergyHonesty: honesty,
                officialRows: official
            )
        case .ev:
            return IncompleteCatalogPrompt(
                isTarget: isTarget,
                body: L10n.incompleteCatalogDataBodyBEV,
                needsFuel: false,
                needsEnergy: true,
                showWeightedEnergyHonesty: false,
                officialRows: []
            )
        case .ice, .hev:
            return IncompleteCatalogPrompt(
                isTarget: isTarget,
                body: L10n.incompleteCatalogDataBodyPHEV,
                needsFuel: true,
                needsEnergy: false,
                showWeightedEnergyHonesty: false,
                officialRows: []
            )
        }
    }

    private func incompleteOfficialBinding(
        key: String,
        isTarget: Bool,
        catalogValuePer100: Double
    ) -> Binding<Double> {
        Binding(
            get: {
                switch key {
                case "fuelConsumptionLPerKm":
                    let override = isTarget
                        ? userInput.targetFuelConsumptionOverrideLPer100Km
                        : userInput.sourceConsumptionOverrideLPer100Km
                    return override ?? catalogValuePer100
                case "energyConsumptionKWhPerKm":
                    let override = isTarget
                        ? userInput.targetEnergyOverrideKWhPer100Km
                        : userInput.sourceEnergyOverrideKWhPer100Km
                    return override ?? catalogValuePer100
                default:
                    return catalogValuePer100
                }
            },
            set: { newValue in
                guard newValue > 0 else { return }
                switch key {
                case "fuelConsumptionLPerKm":
                    if isTarget {
                        userInput.targetFuelConsumptionOverrideLPer100Km = newValue
                    } else {
                        userInput.sourceConsumptionOverrideLPer100Km = newValue
                    }
                case "energyConsumptionKWhPerKm":
                    if isTarget {
                        userInput.targetEnergyOverrideKWhPer100Km = newValue
                    } else {
                        userInput.sourceEnergyOverrideKWhPer100Km = newValue
                    }
                default:
                    break
                }
            }
        )
    }

    private func incompleteFuelBinding(forTarget: Bool) -> Binding<Double> {
        Binding(
            get: {
                if forTarget {
                    return userInput.targetFuelConsumptionOverrideLPer100Km ?? 0
                }
                return userInput.sourceConsumptionOverrideLPer100Km ?? 0
            },
            set: { newValue in
                let stored: Double? = newValue > 0 ? newValue : nil
                if forTarget {
                    userInput.targetFuelConsumptionOverrideLPer100Km = stored
                } else {
                    userInput.sourceConsumptionOverrideLPer100Km = stored
                }
            }
        )
    }

    private func incompleteEnergyBinding(forTarget: Bool) -> Binding<Double> {
        Binding(
            get: {
                if forTarget {
                    return userInput.targetEnergyOverrideKWhPer100Km ?? 0
                }
                return userInput.sourceEnergyOverrideKWhPer100Km ?? 0
            },
            set: { newValue in
                let stored: Double? = newValue > 0 ? newValue : nil
                if forTarget {
                    userInput.targetEnergyOverrideKWhPer100Km = stored
                } else {
                    userInput.sourceEnergyOverrideKWhPer100Km = stored
                }
            }
        )
    }

    private var selectedSourceVehicle: VehicleCatalogItem? {
        sourceVehicles.first(where: { $0.id == userInput.sourceVehicleId })
    }

    private var sourceFuelKind: FuelKind {
        selectedSourceVehicle?.resolvedFuelKind ?? .petrol
    }

    /// Range slider per carburante (GPL 0,5–1,2 €/L; metano €/kg; benzina/diesel 1,0–2,5 €/L).
    private var fuelPriceSliderRange: ClosedRange<Double> {
        switch sourceFuelKind {
        case .lpg: return 0.50...1.20
        case .cng: return 0.80...2.20
        case .diesel, .petrol, .unknown: return 1.0...2.5
        }
    }

    private var fuelPriceSliderStep: Double {
        sourceFuelKind == .lpg || sourceFuelKind == .cng ? 0.02 : 0.05
    }

    private var fuelPriceSliderTitle: String {
        switch sourceFuelKind {
        case .lpg: return L10n.fuelPriceLabelLPG
        case .cng: return L10n.fuelPriceLabelCNG
        case .diesel: return L10n.fuelPriceLabelDiesel
        case .petrol, .unknown: return L10n.fuelPriceLabel
        }
    }

    private var fuelPriceValueLabel: String {
        switch sourceFuelKind {
        case .cng: return String(format: "€%.2f/kg", userInput.fuelPrice)
        default: return String(format: "€%.2f/L", userInput.fuelPrice)
        }
    }

    private var fuelPriceA11yValue: String {
        switch sourceFuelKind {
        case .cng: return L10n.fuelPriceA11yValuePerKg(userInput.fuelPrice)
        default: return L10n.fuelPriceA11yValuePerLiter(userInput.fuelPrice)
        }
    }

    private var targetBrandIsTesla: Bool {
        selectedTargetVehicle?.brand.localizedCaseInsensitiveContains("tesla") ?? false
    }

    private var selectedTargetVehicle: VehicleCatalogItem? {
        targetVehicles.first(where: { $0.id == userInput.targetVehicleId })
    }

    private func loadCatalog() {
        sourceVehicles = VehicleCatalogService.shared.sourceVehicles()
        targetVehicles = VehicleCatalogService.shared.targetEVVehicles()

        // Catalogo ancora in load async: non azzerare gli starter ID (altrimenti CTA → fail-closed).
        guard !sourceVehicles.isEmpty, !targetVehicles.isEmpty else { return }

        if userInput.sourceVehicleId.isEmpty
            || !sourceVehicles.contains(where: { $0.id == userInput.sourceVehicleId }) {
            userInput.sourceVehicleId = preferredId(
                Defaults.starterSourceVehicleId,
                in: sourceVehicles
            ) ?? sourceVehicles.first?.id
                ?? ""
        }
        if userInput.targetVehicleId.isEmpty
            || !targetVehicles.contains(where: { $0.id == userInput.targetVehicleId }) {
            // Preserve UITEST incomplete / partial-PHEV presets even if list timing races.
            if ProcessInfo.processInfo.environment["UITEST_PARTIAL_PHEV_KWH_ONLY"] == "1",
               let forced = VehicleCatalogService.shared.vehicle(by: "bmw-x1-phev-xdrive25e-2024") {
                userInput.targetVehicleId = forced.id
            } else if ProcessInfo.processInfo.environment["UITEST_INCOMPLETE_PHEV"] == "1",
               let forced = VehicleCatalogService.shared.vehicle(by: "jeep-compass-phev-4xe-2022") {
                userInput.targetVehicleId = forced.id
            } else {
                userInput.targetVehicleId = preferredId(
                    Defaults.starterTargetVehicleId,
                    in: targetVehicles
                ) ?? targetVehicles.first?.id
                    ?? ""
            }
        }
    }

    private func preferredId(_ preferred: String, in list: [VehicleCatalogItem]) -> String? {
        list.contains(where: { $0.id == preferred }) ? preferred : nil
    }

    /// €/km di gestione — unica fonte: `OperatingCostCalculator`.
    private func operatingCostPerKm(for vehicle: VehicleCatalogItem) -> Double? {
        let asSource = vehicle.id == userInput.sourceVehicleId
        return OperatingCostCalculator.operatingCostPerKm(
            vehicle: vehicle,
            input: userInput,
            asSource: asSource
        )

    }

    private func validateAndSimulate() {
        validationErrors = InputValidator.validate(userInput)
        if validationErrors.isEmpty {
            showErrors = false
            GrowthTracker.shared.track(.simulationStarted, [
                "scenario": selectedScenario.title,
                "hasHomeCharging": userInput.hasHomeCharging ? "1" : "0",
                "ownershipYears": "\(userInput.ownershipYears)",
            ])
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            onSimulate(selectedScenario)
        } else {
            showErrors = true
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }
}

#Preview {
    NavigationStack {
        InputView(
            userInput: .constant(UserInput(
                dailyKm: 12_000,
                hasHomeCharging: true,
                areaType: .urban,
                fuelPrice: OfficialEnergyCosts.Fallback.petrolPerLiter,
                ownershipYears: 5,
                scenario: .realistic
            )),
            onSimulate: { _ in }
        )
    }
}

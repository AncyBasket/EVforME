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
    @State private var validationErrors: [String] = []
    @State private var showErrors: Bool = false
    @State private var selectedScenario: Scenario = .realistic
    @State private var appearAnimation: Bool = false
    @State private var sourceVehicles: [VehicleCatalogItem] = []
    @State private var targetVehicles: [VehicleCatalogItem] = []
    @State private var showSourceVehiclePicker = false
    @State private var showTargetVehiclePicker = false
    @State private var stickerItem: PhotosPickerItem?
    @State private var stickerStatus: String?
    @State private var stickerBusy = false
    @State private var history: [SavedScenarioSnapshot] = ScenarioHistoryStore.all()
    @State private var showAdvancedDetails = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if showsTopHero {
                    InputScreenHero(appearAnimation: appearAnimation)
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
                            }

                            sliderBlock(
                                title: L10n.fuelPriceLabel,
                                valueLabel: String(format: "€%.2f/L", userInput.fuelPrice),
                                accessibilityLabel: L10n.fuelPriceSliderA11y,
                                accessibilityValue: String(format: "%.2f euros per liter", userInput.fuelPrice)
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
                                    in: 1.0...2.5,
                                    step: 0.05
                                )
                                .tint(.accent)
                            }

                            sliderBlock(
                                title: L10n.electricityPriceLabel,
                                valueLabel: String(format: "€%.2f/kWh", userInput.electricityPricePerKWh),
                                accessibilityLabel: L10n.electricityPriceSliderA11y,
                                accessibilityValue: String(format: "%.2f euros per kWh", userInput.electricityPricePerKWh)
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

                            VStack(alignment: .leading, spacing: 10) {
                                Text(L10n.purchasePricesTitle)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
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
                                Toggle(L10n.includeIncentivesToggle, isOn: $userInput.includeIncentives)
                                    .font(Typography.readingBody)
                                    .tint(.accent)
                                Text(L10n.includeIncentivesHint)
                                    .font(Typography.readingCaption)
                                    .foregroundColor(.secondaryText)
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
                                    || userInput.targetEnergyOverrideKWhPer100Km != nil {
                                    Button(L10n.stickerClearOverride) {
                                        userInput.sourceConsumptionOverrideLPer100Km = nil
                                        userInput.targetEnergyOverrideKWhPer100Km = nil
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
            history = ScenarioHistoryStore.all()
            loadCatalog()
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
        .task {
            await VehicleCatalogService.shared.refreshFromRemoteIfPossible()
            loadCatalog()
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
        }
        .onChange(of: userInput.targetVehicleId) { _, newId in
            guard let vehicle = targetVehicles.first(where: { $0.id == newId }) else { return }
            userInput.targetPurchasePrice = Defaults.suggestedPurchasePrice(for: vehicle)
        }
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
        let restored = item.restoredUserInput()
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

            VStack(spacing: 8) {
                costRow(name: source.displayName, value: costPerKm(for: source), color: .iceLine)
                costRow(name: target.displayName, value: costPerKm(for: target), color: .evLine)
            }
        }
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) {
            Rectangle().fill(Color.hairlineBorder).frame(height: 1)
        }
    }

    private func costRow(name: String, value: Double, color: Color) -> some View {
        HStack {
            Text(name)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .lineLimit(1)
            Spacer()
            Text(String(format: "€%.3f/km", value))
                .font(Typography.readingCardTitle)
                .foregroundColor(color)
                .monospacedDigit()
        }
    }

    private var selectedSourceVehicle: VehicleCatalogItem? {
        sourceVehicles.first(where: { $0.id == userInput.sourceVehicleId })
    }

    private var selectedTargetVehicle: VehicleCatalogItem? {
        targetVehicles.first(where: { $0.id == userInput.targetVehicleId })
    }

    private func loadCatalog() {
        sourceVehicles = VehicleCatalogService.shared.sourceVehicles()
        targetVehicles = VehicleCatalogService.shared.targetEVVehicles()

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
            userInput.targetVehicleId = preferredId(
                Defaults.starterTargetVehicleId,
                in: targetVehicles
            ) ?? targetVehicles.first?.id
                ?? ""
        }
    }

    private func preferredId(_ preferred: String, in list: [VehicleCatalogItem]) -> String? {
        list.contains(where: { $0.id == preferred }) ? preferred : nil
    }

    private func costPerKm(for vehicle: VehicleCatalogItem) -> Double {
        let yearlyKm = max(1.0, Double(userInput.dailyKm))
        let currentYear = Calendar.current.component(.year, from: Date())
        let energyOrFuelCost: Double
        switch vehicle.powertrain {
        case .ice:
            energyOrFuelCost = (vehicle.fuelConsumptionLPerKm ?? 0) * userInput.fuelPrice
        case .ev:
            let kWh = vehicle.resolvedEnergyKWhPerKm ?? 0
            let config = userInput.resolvedChargingConfiguration()
            let annual = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm,
                energyConsumptionKWhPerKm: kWh,
                chargingConfig: config
            )
            energyOrFuelCost = annual / yearlyKm
        case .phev:
            let share = vehicle.phevElectricKmShare(hasHomeCharging: userInput.hasHomeCharging)
            let fuel = (vehicle.fuelConsumptionLPerKm ?? 0) * userInput.fuelPrice * (1 - share)
            let kWh = vehicle.resolvedEnergyKWhPerKm ?? 0
            let annualElec = ChargingCostCalculator.calculateAnnualEnergyCost(
                yearlyKm: yearlyKm * share,
                energyConsumptionKWhPerKm: kWh,
                chargingConfig: userInput.resolvedChargingConfiguration()
            )
            energyOrFuelCost = fuel + (annualElec / yearlyKm)
        }
        let isElectrified = vehicle.powertrain != .ice
        let purchase = vehicle.id == userInput.sourceVehicleId
            ? userInput.sourcePurchasePrice
            : userInput.targetPurchasePrice
        let maintenance = OwnershipCostEstimates.maintenancePerYear(
            purchasePrice: purchase,
            vehicleAge: max(0, currentYear - vehicle.year),
            electrified: isElectrified
        )
        let fixedPerKm = (maintenance + vehicle.taxesPerYear) / yearlyKm
        return energyOrFuelCost + fixedPerKm
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
                fuelPrice: 1.7,
                ownershipYears: 5,
                scenario: .realistic
            )),
            onSimulate: { _ in }
        )
    }
}

//
//  VerdictView.swift
//  EVforME?
//

import SwiftUI
import StoreKit

struct ScrollOffsetKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

struct VerdictView: View {

    let result: SimulationResult
    @Binding var userInput: UserInput
    /// Se valorizzata, il verdetto è presentato come foglio modale con intestazione propria (niente navigation bar di sistema).
    var onDismiss: (() -> Void)?

    @State private var scrollOffset: CGFloat = 0
    @State private var selectedScenario: Scenario
    @State private var currentResult: SimulationResult
    @State private var contentAppeared = false
    @State private var showLeadSheet = false
    @State private var showReportSheet = false
    @State private var aiExplanation: String?
    @State private var aiLoading = false
    @State private var shareCard: ShareableVerdictCard?
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion
    @Environment(\.requestReview) private var requestReview

    private var showsModalChrome: Bool { onDismiss != nil }

    init(result: SimulationResult, userInput: Binding<UserInput>, onDismiss: (() -> Void)? = nil) {
        self.result = result
        self._userInput = userInput
        self.onDismiss = onDismiss
        _selectedScenario = State(initialValue: userInput.wrappedValue.scenario)
        _currentResult = State(initialValue: result)
    }

    private func closeVerdict() {
        if let onDismiss {
            onDismiss()
        } else {
            dismiss()
        }
    }

    private var verdictScrollStack: some View {
        VStack(alignment: .leading, spacing: 28) {
            verdictHeader(result: currentResult)
                .offset(y: accessibilityReduceMotion ? 0 : scrollOffset * 0.04)

            reasonsSection(result: currentResult)

            aiExplanationSection

            scenarioBlock

            // Tre capitoli invece di nove card
            ExpandableSection(
                title: L10n.deepDiveCosts,
                closedDescription: L10n.deepDiveCostsClosed
            ) {
                VStack(alignment: .leading, spacing: 24) {
                    costsDetailSection(result: currentResult)
                    CostSectionView(result: currentResult, scenario: selectedScenario)
                    TimeEvolutionView(scenario: selectedScenario)
                }
            }

            ExpandableSection(
                title: L10n.commonFearsBadge(currentResult.fearReality.count),
                closedDescription: L10n.deepDiveSectionClosed
            ) {
                VStack(alignment: .leading, spacing: 24) {
                    FearVsRealityView(fearRealityItems: currentResult.fearReality)
                    ApprofondimentiView()
                }
            }

            ExpandableSection(
                title: L10n.assumptionsTransparency,
                closedDescription: L10n.sourceCatalogNote
            ) {
                VStack(alignment: .leading, spacing: 24) {
                    assumptionsSection
                    tcoExtrasSection
                    sourcesSection
                    historySection
                }
            }

            Spacer(minLength: 28)

            bottomActions
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 12)
        .opacity(contentAppeared ? 1 : 0)
        .offset(y: contentAppeared ? 0 : (accessibilityReduceMotion ? 0 : 16))
        .animation(
            accessibilityReduceMotion ? .easeOut(duration: 0.16) : .spring(response: 0.5, dampingFraction: 0.88),
            value: contentAppeared
        )
        .coordinateSpace(name: "scroll")
        .overlay(
            GeometryReader { geo in
                Color.clear.preference(key: ScrollOffsetKey.self, value: geo.frame(in: .named("scroll")).minY)
            }
        )
        .onPreferenceChange(ScrollOffsetKey.self) { value in
            scrollOffset = value
        }
    }

    private var verdictModalChrome: some View {
        HStack(alignment: .center, spacing: 14) {
            Button(action: closeVerdict) {
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 36, height: 36)
                    .background(Color.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 4, style: .continuous)
                            .stroke(Color.hairlineBorder, lineWidth: 1)
                    )
            }
            .buttonStyle(.plain)
            .accessibilityLabel(L10n.verdictModalCloseA11y)

            VStack(alignment: .leading, spacing: 2) {
                Text(L10n.appTitle)
                    .font(Typography.sectionEyebrow)
                    .foregroundStyle(Color.ink)
                    .tracking(0.8)
                Text(L10n.verdictModalSubtitle)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(Color.appChrome.opacity(0.94))
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.hairlineBorder)
                .frame(height: 1)
        }
    }

    private var verdictScrollContainer: some View {
        Group {
            if showsModalChrome {
                VStack(spacing: 0) {
                    verdictModalChrome
                    ScrollView {
                        verdictScrollStack
                    }
                    .scrollIndicators(.hidden)
                }
            } else {
                ScrollView {
                    verdictScrollStack
                }
                .scrollIndicators(.hidden)
            }
        }
        .background(ImmersiveBackground().ignoresSafeArea())
    }

    var body: some View {
        Group {
            if showsModalChrome {
                verdictScrollContainer
            } else {
                verdictScrollContainer
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .principal) {
                            Text(L10n.appTitle)
                                .font(Typography.sectionEyebrow)
                                .foregroundColor(.accent)
                                .tracking(0.8)
                        }
                    }
                    .evNavigationChrome()
            }
        }
        .onAppear(perform: runAppearAnimation)
        .onAppear {
            GrowthTracker.shared.track(.verdictShown, [
                "verdict": currentResult.verdict.title,
                "scenario": selectedScenario.title,
            ])
            WidgetSnapshotStore.save(from: currentResult, input: userInput)
            shareCard = VerdictShareCardRenderer.makeCard(result: currentResult, input: userInput)
            ReviewPromptService.recordVerdictShown()
            ReviewPromptService.maybeRequestReview(requestReview)
        }
        .task(id: "\(currentResult.verdict.rawValue)-\(selectedScenario.rawValue)-\(userInput.dailyKm)") {
            await loadAIExplanation()
            shareCard = VerdictShareCardRenderer.makeCard(result: currentResult, input: userInput)
        }
        .sheet(isPresented: $showLeadSheet) {
            LeadCaptureSheet()
        }
        .sheet(isPresented: $showReportSheet) {
            FreeReportSheet(
                result: currentResult,
                userInput: userInput
            )
        }
    }

    private func loadAIExplanation() async {
        aiLoading = true
        defer { aiLoading = false }
        let text = await VerdictExplanationService.explain(result: currentResult, input: userInput)
        aiExplanation = text
    }

    @ViewBuilder
    private var aiExplanationSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.verdictAISectionTitle)
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.8)

            if aiLoading && (aiExplanation == nil || aiExplanation?.isEmpty == true) {
                ProgressView()
                    .tint(Color.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else if let aiExplanation, !aiExplanation.isEmpty {
                Text(aiExplanation)
                    .font(Typography.readingIntro)
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    private func runAppearAnimation() {
        if accessibilityReduceMotion {
            contentAppeared = true
        } else {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.88)) {
                contentAppeared = true
            }
        }
    }

    private var bottomActions: some View {
        VStack(spacing: 10) {
            Group {
                if let shareCard {
                    ShareLink(
                        item: shareCard,
                        subject: Text(L10n.shareSubject),
                        message: Text(L10n.shareMessage),
                        preview: SharePreview(L10n.shareResult, image: Image(uiImage: shareCard.image))
                    ) {
                        shareButtonLabel
                    }
                } else {
                    ShareLink(
                        item: currentResult.shareableText,
                        subject: Text(L10n.shareSubject),
                        message: Text(L10n.shareMessage)
                    ) {
                        shareButtonLabel
                    }
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel(L10n.shareResult)
            .accessibilityHint(L10n.shareLinkA11yHint)

            Button(L10n.exportPDFReport) {
                showReportSheet = true
            }
            .font(Typography.bodyBold)
            .foregroundColor(.ink)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(Color.accent.opacity(0.55))
            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
            .accessibilityHint(L10n.exportPDFA11yHint)

            Button(L10n.talkToAdvisor) {
                showLeadSheet = true
            }
            .font(Typography.bodyBold)
            .foregroundColor(.ink)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .overlay(
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .stroke(Color.ink.opacity(0.3), lineWidth: 1.5)
            )
            .accessibilityHint(L10n.talkToAdvisorA11yHint)

            Button(L10n.modifyInput) {
                closeVerdict()
            }
            .font(Typography.readingCaption.weight(.semibold))
            .foregroundColor(.secondaryText)
            .accessibilityHint(L10n.modifyInputA11yHint)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)

            Button(L10n.liveActivityClear) {
                VerdictLiveActivityController.endAll()
            }
            .font(Typography.readingCaption)
            .foregroundColor(.secondaryText.opacity(0.8))
        }
    }

    private var shareButtonLabel: some View {
        HStack(spacing: 10) {
            Image(systemName: "square.and.arrow.up")
            Text(L10n.shareResult)
        }
        .font(Typography.bodyBold)
        .foregroundStyle(Color.ctaLabel)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color.ctaFill)
        .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.accent)
                .frame(height: 3)
        }
    }

    private func verdictHeader(result: SimulationResult) -> some View {
        let tint = verdictTint(result.verdict)
        let source = VehicleCatalogService.shared.vehicle(by: userInput.sourceVehicleId)
        let target = VehicleCatalogService.shared.vehicle(by: userInput.targetVehicleId)

        return VStack(alignment: .leading, spacing: 18) {
            Capsule()
                .fill(tint)
                .frame(width: 56, height: 5)

            Text(result.verdict.title)
                .font(Typography.verdictTitle)
                .foregroundColor(.ink)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
                .minimumScaleFactor(0.72)

            Text(result.verdict.description)
                .font(Typography.readingIntro)
                .foregroundColor(.secondaryText)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)

            if let source, let target {
                Text(L10n.verdictCompareLine(source.displayName, target.displayName))
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Prova numerica immediata — il cuore di un decision tool di riferimento.
            HStack(alignment: .top, spacing: 0) {
                verdictProofMetric(
                    value: L10n.verdictProofSavingsValue(
                        result.yearlySavingsRange.lowerBound,
                        result.yearlySavingsRange.upperBound
                    ),
                    label: L10n.verdictProofSavingsLabel
                )
                Rectangle()
                    .fill(Color.hairlineBorder)
                    .frame(width: 1)
                    .padding(.vertical, 4)
                verdictProofMetric(
                    value: "\(result.weeklyCharges)×",
                    label: L10n.verdictProofChargesLabel
                )
                Rectangle()
                    .fill(Color.hairlineBorder)
                    .frame(width: 1)
                    .padding(.vertical, 4)
                verdictProofMetric(
                    value: result.breakEvenMonths.map { L10n.verdictProofBreakEvenValue($0) } ?? "—",
                    label: L10n.verdictProofBreakEvenLabel
                )
            }
            .padding(.vertical, 14)
            .padding(.horizontal, 4)
            .overlay(alignment: .top) {
                Rectangle().fill(Color.hairlineBorder).frame(height: 1)
            }
            .overlay(alignment: .bottom) {
                Rectangle().fill(Color.hairlineBorder).frame(height: 1)
            }

            Text(L10n.verdictTrustStrip)
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 12)
        .padding(.bottom, 4)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
        .accessibilityLabel(
            [
                result.verdict.title,
                result.verdict.description,
                L10n.verdictProofSavingsValue(
                    result.yearlySavingsRange.lowerBound,
                    result.yearlySavingsRange.upperBound
                ),
                L10n.verdictProofSavingsLabel,
                "\(result.weeklyCharges)×",
                L10n.verdictProofChargesLabel,
                result.breakEvenMonths.map { L10n.verdictProofBreakEvenValue($0) } ?? "",
                L10n.verdictTrustStrip
            ]
            .filter { !$0.isEmpty }
            .joined(separator: ". ")
        )
    }

    private func verdictProofMetric(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(Typography.verdictMetricValue)
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label.uppercased())
                .font(Typography.verdictMetricLabel)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.5)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 10)
    }

    private func verdictTint(_ verdict: EVVerdict) -> Color {
        switch verdict {
        case .yes: return .accent
        case .maybe: return .warning
        case .notYet: return .secondaryText
        }
    }

    private func reasonsSection(result: SimulationResult) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(L10n.why.uppercased())
                .font(Typography.sectionEyebrow)
                .foregroundColor(.secondaryText)
                .tracking(1.0)

            ForEach(result.keyReasons.indices, id: \.self) { i in
                HStack(alignment: .top, spacing: 12) {
                    Text(String(format: "%02d", i + 1))
                        .font(Typography.sectionEyebrow)
                        .foregroundStyle(Color.accentDark)
                        .frame(width: 28, alignment: .leading)
                    Text(result.keyReasons[i])
                        .font(Typography.readingBody)
                        .foregroundColor(.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func costsDetailSection(result: SimulationResult) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(L10n.deepDiveCostsExplanation)
                .font(Typography.readingBody)
                .foregroundColor(.secondaryText)
                .padding(.bottom, 4)

            CostsComparisonView(
                comparison: result.yearlyComparison,
                userInput: userInput,
                weeklyCharges: result.weeklyCharges,
                sourceBreakdown: result.sourceYearlyBreakdown,
                targetBreakdown: result.targetYearlyBreakdown
            )

            HStack(alignment: .center, spacing: 12) {
                Text(L10n.deepDiveCostsTakeaway)
                    .font(Typography.title2)
                    .foregroundColor(.ink)
            }
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .overlay(alignment: .leading) {
                Rectangle()
                    .fill(Color.accent)
                    .frame(width: 3)
                    .padding(.leading, -10)
            }
        }
    }

    private var assumptionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            assumptionRow(text: L10n.assumptionCalculationsEstimates)
            assumptionRow(text: L10n.assumptionNoDataSent)
            assumptionRow(text: L10n.assumptionAveragePrices)
            assumptionRow(text: L10n.assumptionConsumptionGas)
            assumptionRow(text: L10n.assumptionConsumptionEv)
            assumptionRow(text: L10n.assumptionMaintenance)
            assumptionRow(text: L10n.assumptionTaxes)
            assumptionRow(text: L10n.assumptionElectricity)
            assumptionRow(text: L10n.incentivesTransparencyNote)
        }
    }

    private var tcoExtrasSection: some View {
        let years = max(1, userInput.ownershipYears)
        let km = Double(userInput.dailyKm)
        let sourceElectrified = VehicleCatalogService.shared.vehicle(by: userInput.sourceVehicleId).map { $0.powertrain != .ice } ?? false
        let iceIns = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: userInput.sourcePurchasePrice,
            yearlyKm: km,
            electrified: sourceElectrified
        )
        let evIns = OwnershipCostEstimates.insurancePerYear(
            purchasePrice: userInput.targetPurchasePrice,
            yearlyKm: km,
            electrified: true
        )
        let iceRes = OwnershipCostEstimates.residualValue(
            purchasePrice: userInput.sourcePurchasePrice,
            years: years,
            electrified: sourceElectrified
        )
        let evRes = OwnershipCostEstimates.residualValue(
            purchasePrice: userInput.targetPurchasePrice,
            years: years,
            electrified: true
        )
        return VStack(alignment: .leading, spacing: 12) {
            Text(L10n.tcoExtrasIntro)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
            assumptionRow(text: L10n.tcoInsuranceRow(Int(iceIns), Int(evIns)))
            assumptionRow(text: L10n.tcoResidualRow(years, Int(iceRes), Int(evRes)))
            assumptionRow(text: L10n.tcoResidualNote)
        }
    }

    private var sourcesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            assumptionRow(text: L10n.sourceCatalogNote)
            assumptionRow(text: L10n.sourcePricesNote)
            assumptionRow(text: L10n.incentivesTransparencyNote)
        }
    }

    private var historySection: some View {
        let items = ScenarioHistoryStore.all()
        return Group {
            if items.isEmpty {
                Text(L10n.historyEmpty)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    Text(L10n.historyRestoreHint)
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                    ForEach(items) { item in
                        Button {
                            let restored = item.restoredUserInput()
                            userInput = restored
                            selectedScenario = restored.scenario
                            if let simulated = EVSimulator.simulate(input: restored) {
                                currentResult = simulated
                                StorageService.shared.saveUserInput(restored)
                                WidgetSnapshotStore.save(from: simulated, input: restored)
                                VerdictLiveActivityController.publish(from: simulated, input: restored)
                                shareCard = VerdictShareCardRenderer.makeCard(result: simulated, input: restored)
                            }
                            aiExplanation = nil
                            UISelectionFeedbackGenerator().selectionChanged()
                        } label: {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.verdictTitle)
                                        .font(Typography.readingCardTitle)
                                        .foregroundColor(.primaryText)
                                    Text("\(L10n.yearlyKmValue(item.yearlyKm)) · €\(item.savingsMin)–€\(item.savingsMax)")
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                }
                                Spacer()
                                if let months = item.breakEvenMonths {
                                    Text(L10n.breakEvenMonthsBadge(months))
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                }
                                Image(systemName: "arrow.uturn.backward.circle.fill")
                                    .foregroundStyle(Color.accent)
                            }
                            .padding(.vertical, 4)
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint(L10n.historyRestoreHint)
                    }
                }
            }
        }
    }

    private func assumptionRow(text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "info.circle.fill")
                .font(.system(size: 16))
                .foregroundColor(.accent.opacity(0.85))
            Text(text)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
        }
    }

    private var scenarioBlock: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(L10n.scenarioTitle)
                .font(Typography.readingCardTitle)
                .foregroundColor(.primaryText)

            HStack(spacing: 8) {
                ForEach(Scenario.allCases) { scenario in
                    let selected = selectedScenario == scenario
                    Button {
                        let anim: Animation = accessibilityReduceMotion
                            ? .easeOut(duration: 0.18)
                            : .spring(response: 0.35, dampingFraction: 0.78)
                        withAnimation(anim) {
                            selectedScenario = scenario
                            updateResultForScenario(scenario)
                        }
                        UISelectionFeedbackGenerator().selectionChanged()
                    } label: {
                        Text(scenario.title)
                            .font(Typography.readingCaption.weight(.semibold))
                            .padding(.vertical, 11)
                            .padding(.horizontal, 8)
                            .frame(maxWidth: .infinity)
                            .background(
                                RoundedRectangle(cornerRadius: 4, style: .continuous)
                                    .fill(selected ? Color.ctaFill : Color.clear)
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 4, style: .continuous)
                                    .stroke(selected ? Color.ctaFill : Color.hairlineBorder, lineWidth: 1.5)
                            )
                            .foregroundColor(selected ? Color.ctaLabel : Color.ink)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(scenario.title)
                    .accessibilityHint(L10n.scenarioChipA11yHint)
                    .accessibilityAddTraits(selected ? .isSelected : [])
                }
            }

            Text(selectedScenario.scenarioDescription)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
        }
        .evCardStyle()
    }

    private func updateResultForScenario(_ scenario: Scenario) {
        userInput.scenario = scenario
        guard let simulated = EVSimulator.simulate(input: userInput, scenario: scenario) else { return }
        currentResult = simulated
        aiExplanation = nil
        StorageService.shared.saveUserInput(userInput)
        WidgetSnapshotStore.save(from: simulated, input: userInput)
        VerdictLiveActivityController.publish(from: simulated, input: userInput)
        shareCard = VerdictShareCardRenderer.makeCard(result: simulated, input: userInput)
    }
}

private struct LeadCaptureSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var email = ""
    @State private var city = ""
    @State private var consent = true
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
        if Defaults.leadWebhookURL.isEmpty {
            sendNote = L10n.leadSavedLocally
        } else {
            sendNote = remoteOK ? L10n.leadSentRemote : L10n.leadSendFailed
        }
        try? await Task.sleep(nanoseconds: 450_000_000)
        dismiss()
    }
}

private struct FreeReportSheet: View {
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

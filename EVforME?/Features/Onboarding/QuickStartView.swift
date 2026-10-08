//
//  QuickStartView.swift
//  EVforME?
//
//  Prima schermata: risposta in ~30 secondi (auto attuale, km/giorno, ricarica casa).
//

import SwiftUI

struct QuickStartView: View {
    @Binding var userInput: UserInput
    var onVerdict: (Scenario) -> Void
    var onCustomize: () -> Void

    @State private var appear = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var sourceList: [VehicleCatalogItem] {
        VehicleCatalogService.shared.sourceVehicles()
    }

    var body: some View {
        ZStack {
            ImmersiveBackground()
            VStack(spacing: 0) {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 24) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(L10n.appTitle)
                                .font(Typography.display)
                                .foregroundStyle(Color.ink)
                            Text(L10n.quickStartThirtySecondTitle)
                                .font(Typography.readingIntro)
                                .foregroundStyle(Color.secondaryText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.top, 28)

                        VStack(alignment: .leading, spacing: 8) {
                            Text(L10n.quickStartCurrentCar)
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.secondaryText)
                            Picker(L10n.quickStartCurrentCar, selection: $userInput.sourceVehicleId) {
                                ForEach(sourceList.prefix(80)) { vehicle in
                                    Text(vehicle.displayName).tag(vehicle.id)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(Color.ink)
                        }

                        VStack(alignment: .leading, spacing: 8) {
                            Text(L10n.dailyKmQuestion)
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.secondaryText)
                            Text(L10n.yearlyKmValue(userInput.dailyKm))
                                .font(Typography.metric)
                                .foregroundStyle(Color.ink)
                            Slider(
                                value: Binding(
                                    get: { Double(userInput.dailyKm) },
                                    set: { userInput.dailyKm = Int($0.rounded()) }
                                ),
                                in: 1_000...80_000,
                                step: 500
                            )
                            .tint(Color.ink)
                        }

                        Toggle(isOn: $userInput.hasHomeCharging) {
                            Text(L10n.homeChargingToggle)
                                .font(Typography.title2)
                                .foregroundStyle(Color.ink)
                        }
                        .tint(Color.accentDark)

                        Text(L10n.quickStartThirtySecondHint)
                            .font(Typography.readingCaption)
                            .foregroundStyle(Color.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)

                        Spacer(minLength: 24)
                    }
                    .padding(.horizontal, 24)
                    .opacity(appear ? 1 : 0)
                    .offset(y: appear ? 0 : 12)
                }

                VStack(spacing: 12) {
                    PrimaryButton(title: L10n.quickStartSeeVerdict, action: runQuickVerdict)
                    Button(L10n.quickStartCustomize) {
                        onCustomize()
                    }
                    .font(Typography.readingCaption.weight(.semibold))
                    .foregroundStyle(Color.secondaryText)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 28)
                .padding(.top, 8)
            }
        }
        .onAppear {
            ensureDefaults()
            if reduceMotion {
                appear = true
            } else {
                withAnimation(.spring(response: 0.5, dampingFraction: 0.9)) {
                    appear = true
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .evVehicleCatalogDidUpdate)) { _ in
            ensureDefaults()
        }
    }

    private func ensureDefaults() {
        if userInput.sourceVehicleId.isEmpty || VehicleCatalogService.shared.vehicle(by: userInput.sourceVehicleId) == nil {
            userInput.sourceVehicleId = sourceList.first?.id ?? Defaults.starterSourceVehicleId
        }
        if userInput.targetVehicleId.isEmpty || VehicleCatalogService.shared.vehicle(by: userInput.targetVehicleId) == nil {
            userInput.targetVehicleId = VehicleCatalogService.shared.targetEVVehicles().first?.id
                ?? Defaults.starterTargetVehicleId
        }
        userInput.scenario = .realistic
        userInput.comparisonIntent = .alreadyOwned
        userInput.ownershipYears = 5
        userInput.areaType = .mixed
        userInput.tripProfile = .custom
        userInput.chargingConfiguration = ChargingCostCalculator.suggestedConfiguration(
            yearlyKm: Double(userInput.dailyKm),
            hasHomeCharging: userInput.hasHomeCharging
        )
    }

    private func runQuickVerdict() {
        ensureDefaults()
        // Suggerisci un EV target tipico se ancora sul default.
        if let suggested = VehicleCatalogService.shared.targetEVVehicles().first(where: {
            $0.id.contains("model-3") || $0.id.contains("mg4") || $0.id.contains("500e")
        }) {
            userInput.targetVehicleId = suggested.id
        }
        StorageService.shared.saveUserInput(userInput)
        StorageService.shared.markOnboardingSeen()
        GrowthTracker.shared.track(.onboardingCompleted, ["path": "thirty_second"])
        onVerdict(.realistic)
    }
}

//
//  QuickStartView.swift
//  EVforME?
//
//  Prima schermata: risposta in ~30 secondi (auto attuale, km/giorno, ricarica casa, paese).
//

import SwiftUI

struct QuickStartView: View {
    @Binding var userInput: UserInput
    var onVerdict: (Scenario) -> Void
    var onCustomize: () -> Void

    @State private var appear = false
    @State private var showSourcePicker = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var sourceList: [VehicleCatalogItem] {
        VehicleCatalogService.shared.sourceVehicles()
    }

    private var selectedSourceName: String {
        VehicleCatalogService.shared.vehicle(by: userInput.sourceVehicleId)?.displayName
            ?? L10n.vehiclePairTapToChoose
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
                            Button {
                                showSourcePicker = true
                            } label: {
                                HStack {
                                    Text(selectedSourceName)
                                        .font(Typography.title2)
                                        .foregroundStyle(Color.ink)
                                        .multilineTextAlignment(.leading)
                                    Spacer()
                                    Image(systemName: "chevron.up.chevron.down")
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(Color.secondaryText)
                                }
                                .padding(.vertical, 12)
                                .padding(.horizontal, 14)
                                .background(Color.ink.opacity(0.06))
                                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(L10n.quickStartCurrentCar)
                            .accessibilityValue(selectedSourceName)
                        }

                        VStack(alignment: .leading, spacing: 8) {
                            Text(L10n.marketPickerLabel)
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.secondaryText)
                            Picker(L10n.marketPickerLabel, selection: $userInput.market) {
                                ForEach(AppMarket.pickerCases) { market in
                                    Text(market.localizedName).tag(market)
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
        .sheet(isPresented: $showSourcePicker) {
            VehicleCatalogPickerSheet(
                title: L10n.quickStartCurrentCar,
                vehicles: sourceList,
                selectedId: $userInput.sourceVehicleId
            )
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
        // Non sovrascrivere un target già scelto dall’utente.
        if userInput.targetVehicleId.isEmpty || VehicleCatalogService.shared.vehicle(by: userInput.targetVehicleId) == nil {
            userInput.targetVehicleId = ""
        }
        // Non resettare scenario / ricarica già scelti dall’utente.
        if userInput.ownershipYears <= 0 {
            userInput.ownershipYears = 5
        }
    }

    private func runQuickVerdict() {
        ensureDefaults()
        // Suggerisci Model 3 / MG4 / 500e solo se il target è ancora vuoto.
        if userInput.targetVehicleId.isEmpty {
            if let suggested = VehicleCatalogService.shared.targetEVVehicles().first(where: {
                $0.id.contains("model-3") || $0.id.contains("mg4") || $0.id.contains("500e")
            }) {
                userInput.targetVehicleId = suggested.id
            } else {
                userInput.targetVehicleId = VehicleCatalogService.shared.targetEVVehicles().first?.id
                    ?? Defaults.starterTargetVehicleId
            }
        }
        StorageService.shared.saveUserInput(userInput)
        StorageService.shared.markOnboardingSeen()
        GrowthTracker.shared.track(.onboardingCompleted, ["path": "thirty_second"])
        // Usa lo scenario già scelto (default iniziale: realistic in UserInput).
        onVerdict(userInput.scenario)
    }
}

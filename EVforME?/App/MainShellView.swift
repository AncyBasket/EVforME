//
//  MainShellView.swift
//  EVforME?
//
//  Guscio principale: niente NavigationStack “anonimo”, tab custom + verdetto a tutto schermo.
//

import SwiftUI

enum AppShellTab: String, CaseIterable, Identifiable {
    case workshop
    case guides

    var id: String { rawValue }
}

struct MainShellView: View {
    @Binding var userInput: UserInput
    @Binding var simulationResult: SimulationResult?
    @Binding var isLoading: Bool
    @Binding var showOnboarding: Bool

    var onSimulate: (Scenario) -> Void
    var catalogSetup: () async -> Void
    var onReopenLastComparison: () -> Void = {}
    var onRecalculateLastComparison: () -> Void = {}

    @State private var selectedTab: AppShellTab = .workshop
    @State private var showGrowthDebug = false
    /// Prima schermata di benvenuto (una sola volta per sessione di onboarding).
    @State private var showWelcomeBeforeQuickStart = true
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    private var tabSwitchAnimation: Animation {
        accessibilityReduceMotion
            ? .easeInOut(duration: 0.18)
            : .spring(response: 0.46, dampingFraction: 0.86)
    }

    var body: some View {
        ZStack {
            ImmersiveBackground()

            VStack(spacing: 0) {
                ZStack {
                    if selectedTab == .workshop {
                        InputView(
                            userInput: $userInput,
                            useNavigationChrome: false,
                            showsTopHero: true,
                            onSimulate: onSimulate,
                            onReopenLastComparison: onReopenLastComparison,
                            onRecalculateLastComparison: onRecalculateLastComparison
                        )
                        .transition(tabEnter(.leading, exit: .trailing))
                    }
                    if selectedTab == .guides {
                        GuidesHubView()
                            .transition(tabEnter(.trailing, exit: .leading))
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .animation(tabSwitchAnimation, value: selectedTab)

                ShellTabStrip(selection: $selectedTab)
            }

            if isLoading {
                LoadingView()
            }

#if DEBUG
            VStack {
                HStack {
                    Spacer()
                    Button {
                        showGrowthDebug = true
                    } label: {
                        Image(systemName: "ladybug.fill")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Color.ink)
                            .padding(10)
                            .background(Color.accent.opacity(0.85))
                            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                    }
                    .padding(.top, 12)
                    .padding(.trailing, 14)
                }
                Spacer()
            }
#endif
        }
        .tint(Color.accentDark)
        .onAppear {
            guard ProcessInfo.processInfo.environment["UITEST_PRESET_VEHICLES"] == "1" else { return }
            userInput.sourceVehicleId = Defaults.starterSourceVehicleId
            if ProcessInfo.processInfo.environment["UITEST_PARTIAL_BOLLO"] == "1" {
                // EV ≥ 5 anni senza P.2 → header “Totale parziale (bollo non stimato)”.
                userInput.targetVehicleId = "tesla-model-3-2020"
                userInput.targetBookletPowerKwP2 = nil
            } else {
                userInput.targetVehicleId = Defaults.starterTargetVehicleId
            }
            if ProcessInfo.processInfo.environment["UITEST_SOURCE_FUEL"] == "lpg" {
                userInput.sourceVehicleId = "dacia-sandero-eco-g-2022"
            }
            if ProcessInfo.processInfo.environment["UITEST_PARTIAL_PHEV_KWH_ONLY"] == "1" {
                // PHEV con CS/range/batteria ufficiali: chiede solo kWh, poi verdetto.
                userInput.targetVehicleId = "bmw-x1-phev-xdrive25e-2024"
            } else if ProcessInfo.processInfo.environment["UITEST_INCOMPLETE_PHEV"] == "1" {
                // PHEV ancora senza CS/CD ufficiali → chiede consumi, niente verdetto.
                userInput.targetVehicleId = "jeep-compass-phev-4xe-2022"
            }
            if let raw = ProcessInfo.processInfo.environment["UITEST_FUEL_PRICE"],
               let price = Double(raw.replacingOccurrences(of: ",", with: ".")) {
                userInput.fuelPrice = price
                // Evita che applyOfficialCosts / sync sovrascrivano il preset (es. 0,78 GPL).
                StorageService.shared.markFuelPriceCustomized()
            }
        }
        .task { await catalogSetup() }
        .fullScreenCover(isPresented: $showOnboarding, onDismiss: {
            showWelcomeBeforeQuickStart = true
        }) {
            if showWelcomeBeforeQuickStart {
                OnboardingView(
                    userInput: $userInput,
                    onContinue: {
                        StorageService.shared.saveUserInput(userInput)
                        showWelcomeBeforeQuickStart = false
                    },
                    onSkip: {
                        // Salta il benvenuto e passa al percorso rapido (sempre prima volta).
                        StorageService.shared.saveUserInput(userInput)
                        showWelcomeBeforeQuickStart = false
                    }
                )
            } else {
                QuickStartView(
                    userInput: $userInput,
                    onVerdict: { scenario in
                        showOnboarding = false
                        onSimulate(scenario)
                    },
                    onCustomize: {
                        StorageService.shared.saveUserInput(userInput)
                        StorageService.shared.markOnboardingSeen()
                        GrowthTracker.shared.track(.onboardingCompleted, ["path": "customize"])
                        showOnboarding = false
                    }
                )
            }
        }
        .fullScreenCover(isPresented: Binding(
            get: { simulationResult != nil },
            set: { if !$0 { simulationResult = nil } }
        )) {
            Group {
                if let result = simulationResult {
                    VerdictView(
                        result: result,
                        userInput: $userInput,
                        onDismiss: { simulationResult = nil }
                    )
                    .presentationDragIndicator(.visible)
                }
            }
        }
#if DEBUG
        .sheet(isPresented: $showGrowthDebug) {
            GrowthDebugView()
        }
#endif
        .withErrorHandling()
        .onReceive(NotificationCenter.default.publisher(for: .catalogVehicleSelectionRequested)) { _ in
            simulationResult = nil
            selectedTab = .workshop
        }
    }

    private func tabEnter(_ insertEdge: Edge, exit removalEdge: Edge) -> AnyTransition {
        if accessibilityReduceMotion {
            return .opacity
        }
        return .asymmetric(
            insertion: .move(edge: insertEdge).combined(with: .opacity),
            removal: .move(edge: removalEdge).combined(with: .opacity)
        )
    }
}

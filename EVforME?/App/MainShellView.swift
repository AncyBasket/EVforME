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

    @State private var selectedTab: AppShellTab = .workshop
    @State private var showGrowthDebug = false
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
                            onSimulate: onSimulate
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
            userInput.targetVehicleId = Defaults.starterTargetVehicleId
        }
        .task { await catalogSetup() }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingView(
                userInput: $userInput,
                onContinue: {
                    StorageService.shared.saveUserInput(userInput)
                    StorageService.shared.markOnboardingSeen()
                    GrowthTracker.shared.track(.onboardingCompleted, ["path": "quick_start"])
                    showOnboarding = false
                },
                onSkip: {
                    StorageService.shared.saveUserInput(userInput)
                    StorageService.shared.markOnboardingSeen()
                    GrowthTracker.shared.track(.onboardingCompleted, ["path": "skip"])
                    showOnboarding = false
                }
            )
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

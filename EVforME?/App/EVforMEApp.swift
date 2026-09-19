//
//  EVforMEApp.swift
//  EVforME?
//

import SwiftUI

@main
struct EVforMEApp: App {
    @State private var userInput: UserInput = {
        let defaultInput = UserInput(
            dailyKm: 12000,
            hasHomeCharging: true,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            scenario: .realistic
        )
        // Initialize with suggested charging configuration
        var configuredInput = defaultInput
        configuredInput.chargingConfiguration = ChargingCostCalculator.suggestedConfiguration(
            yearlyKm: Double(defaultInput.dailyKm),
            hasHomeCharging: defaultInput.hasHomeCharging
        )
        return configuredInput
    }()

    @State private var simulationResult: SimulationResult?
    @State private var isLoading: Bool = false
    @State private var showOnboarding: Bool = !StorageService.shared.hasSeenOnboarding
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            MainShellView(
                userInput: $userInput,
                simulationResult: $simulationResult,
                isLoading: $isLoading,
                showOnboarding: $showOnboarding,
                onSimulate: simulateWithLoading,
                catalogSetup: {
                    guard !Self.isRunningUnderXCTest else { return }
                    await refreshLiveData(applyCosts: true)
                }
            )
            .task {
                syncFuelFromWidgetIfNeeded()
                if !Self.isRunningUnderXCTest {
                    await refreshLiveData(applyCosts: true)
                }
                if AppDeepLink.consumeOpenLastVerdictRequest() {
                    openLastVerdict()
                }
            }
            .onChange(of: scenePhase) { _, phase in
                guard phase == .active else { return }
                syncFuelFromWidgetIfNeeded(reopenVerdictIfNeeded: simulationResult != nil)
                guard !Self.isRunningUnderXCTest else { return }
                Task { await refreshLiveData(applyCosts: true) }
            }
            .onOpenURL { url in
                guard AppDeepLink.matches(url) else { return }
                openLastVerdict()
            }
        }
    }

    /// Unit-test host also launches the app; skip live refresh to avoid racing the suite.
    private static var isRunningUnderXCTest: Bool {
        ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil
    }

    /// Catalogo + prezzi energia + incentivi IT a ogni cold start / foreground.
    /// Best-effort rete; offline → cache/bundle. Non sovrascrive prezzi customizzati a mano.
    private func refreshLiveData(applyCosts: Bool) async {
        AppLogger.shared.info("Live data refresh starting (applyCosts=\(applyCosts))", category: .network)

        VehicleCatalogService.shared.setRemoteCatalogURL(Defaults.vehicleCatalogRemoteURL)
        async let catalogRefresh: Void = VehicleCatalogService.shared.refreshFromRemoteIfPossible()
        async let incentives = ItalianIncentivesService.shared.refresh()
        async let costs = OfficialCostService.shared.fetchLatest()

        _ = await catalogRefresh
        let schedule = await incentives
        AppLogger.shared.info(
            "Incentives ready (updatedAt=\(schedule.updatedAt ?? "n/a"), lastFetch=\(ItalianIncentivesService.shared.lastSuccessfulFetchDate?.description ?? "none"))",
            category: .network
        )

        guard applyCosts else {
            AppLogger.shared.info("Live data refresh done (costs skipped)", category: .network)
            return
        }

        guard let costs = await costs else {
            AppLogger.shared.warning("Official energy costs unavailable — keeping last values", category: .network)
            return
        }
        AppLogger.shared.info(
            "Official costs ready fuel=\(costs.fuelPricePerLiter) elec=\(costs.electricityPricePerKWh) updatedAt=\(costs.updatedAt ?? "n/a")",
            category: .network
        )

        var updated = userInput
        if StorageService.shared.applyOfficialCostsIfNeeded(costs, to: &updated) {
            userInput = updated
            StorageService.shared.saveUserInput(updated)
            if let result = EVSimulator.simulate(input: updated) {
                WidgetSnapshotStore.save(from: result, input: updated)
            }
            AppLogger.shared.info("Applied official costs to user input", category: .network)
        } else {
            AppLogger.shared.info("Official costs unchanged or user-customized — no overwrite", category: .network)
        }
        AppLogger.shared.info("Live data refresh done", category: .network)
    }

    private func syncFuelFromWidgetIfNeeded(reopenVerdictIfNeeded: Bool = false) {
        StorageService.shared.importWidgetFuelCustomizationFlag()
        guard let mirrored = WidgetSnapshotStore.loadMirroredUserInput(),
              abs(mirrored.fuelPrice - userInput.fuelPrice) > 0.001 else {
            return
        }
        var updated = userInput
        updated.fuelPrice = mirrored.fuelPrice
        userInput = updated
        StorageService.shared.markFuelPriceCustomized()
        StorageService.shared.saveUserInput(updated)
        if reopenVerdictIfNeeded, let result = EVSimulator.simulate(input: updated) {
            simulationResult = result
            WidgetSnapshotStore.save(from: result, input: updated)
        }
    }

    private func simulateWithLoading(scenario: Scenario) {
        isLoading = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            var input = userInput
            input.scenario = scenario
            input.chargingConfiguration = input.resolvedChargingConfiguration()
            userInput = input
            StorageService.shared.saveUserInput(input)
            guard let result = EVSimulator.simulate(input: input, scenario: scenario) else {
                simulationResult = nil
                isLoading = false
                return
            }
            simulationResult = result
            ScenarioHistoryStore.save(result: result, input: input)
            WidgetSnapshotStore.save(from: result, input: input)
            VerdictLiveActivityController.publish(from: result, input: input)
            isLoading = false
        }
    }

    private func openLastVerdict() {
        showOnboarding = false
        if userInput.sourceVehicleId.isEmpty {
            userInput.sourceVehicleId = VehicleCatalogService.shared.sourceVehicles().first?.id
                ?? "alfa-romeo-147-2005"
        }
        if userInput.targetVehicleId.isEmpty {
            userInput.targetVehicleId = VehicleCatalogService.shared.targetEVVehicles().first?.id
                ?? "audi-q4-e-tron-2017"
        }
        syncFuelFromWidgetIfNeeded()
        guard let result = EVSimulator.simulate(input: userInput) else { return }
        simulationResult = result
        WidgetSnapshotStore.save(from: result, input: userInput)
        VerdictLiveActivityController.publish(from: result, input: userInput)
    }
}

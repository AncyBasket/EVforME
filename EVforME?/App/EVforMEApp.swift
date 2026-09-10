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
                    await refreshLiveData(applyCosts: true)
                }
            )
            .task {
                syncFuelFromWidgetIfNeeded()
                await refreshLiveData(applyCosts: true)
                if AppDeepLink.consumeOpenLastVerdictRequest() {
                    openLastVerdict()
                }
            }
            .onChange(of: scenePhase) { _, phase in
                guard phase == .active else { return }
                syncFuelFromWidgetIfNeeded(reopenVerdictIfNeeded: simulationResult != nil)
                Task { await refreshLiveData(applyCosts: true) }
            }
            .onOpenURL { url in
                guard AppDeepLink.matches(url) else { return }
                openLastVerdict()
            }
        }
    }

    /// Catalogo remoto (CDN pubblico) + prezzi MIMIT/Eurostat a ogni apertura / foreground.
    private func refreshLiveData(applyCosts: Bool) async {
        VehicleCatalogService.shared.setRemoteCatalogURL(Defaults.vehicleCatalogRemoteURL)
        await VehicleCatalogService.shared.refreshFromRemoteIfPossible()

        guard applyCosts,
              let costs = await OfficialCostService.shared.fetchLatest() else { return }
        var updated = userInput
        if StorageService.shared.applyOfficialCostsIfNeeded(costs, to: &updated) {
            userInput = updated
            StorageService.shared.saveUserInput(updated)
            if let result = EVSimulator.simulate(input: updated) {
                WidgetSnapshotStore.save(from: result, input: updated)
            }
        }
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

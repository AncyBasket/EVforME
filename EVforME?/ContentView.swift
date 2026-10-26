//
//  ContentView.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import SwiftUI

struct ContentView: View {
    @State private var userInput = UserInput(
        dailyKm: 12000,
        hasHomeCharging: true,
        areaType: .urban,
        fuelPrice: OfficialEnergyCosts.Fallback.petrolPerLiter,
        ownershipYears: 5,
        sourceVehicleId: "",
        targetVehicleId: "",
        scenario: .realistic
    )
    @State private var simulationResult: SimulationResult?
    @State private var isLoading = false
    @State private var showOnboarding = false

    var body: some View {
        MainShellView(
            userInput: $userInput,
            simulationResult: $simulationResult,
            isLoading: $isLoading,
            showOnboarding: $showOnboarding,
            onSimulate: { scenario in
                isLoading = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) {
                    simulationResult = EVSimulator.simulate(input: userInput, scenario: scenario)
                    isLoading = false
                }
            },
            catalogSetup: {
                await VehicleCatalogService.shared.refreshFromRemoteIfPossible()
            }
        )
        .onAppear {
            // Solo UI test: evita flussi lunghi nel catalogo; nessun effetto in release normale.
            guard ProcessInfo.processInfo.environment["UITEST_PRESET_VEHICLES"] == "1" else { return }
            if userInput.sourceVehicleId.isEmpty {
                userInput.sourceVehicleId = "alfa-romeo-147-2005"
            }
            if ProcessInfo.processInfo.environment["UITEST_PARTIAL_BOLLO"] == "1" {
                userInput.targetVehicleId = "tesla-model-3-2020"
                userInput.targetBookletPowerKwP2 = nil
            } else if userInput.targetVehicleId.isEmpty {
                userInput.targetVehicleId = "audi-q4-e-tron-2021"
            }
        }
#if DEBUG
        .onChange(of: userInput.targetVehicleId) { _, newId in
            // UITEST version picker: open verdict after an EEA version id is chosen
            // (avoids flaky bottom-CTA taps under the catalog sheet).
            guard ProcessInfo.processInfo.environment["UITEST_OPEN_TARGET_PICKER"] == "1",
                  newId.range(of: #"-v\d"#, options: .regularExpression) != nil else { return }
            isLoading = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) {
                let input = userInput
                simulationResult = EVSimulator.simulate(input: input, scenario: input.scenario)
                isLoading = false
            }
        }
#endif
    }
}

#Preview {
    ContentView()
}

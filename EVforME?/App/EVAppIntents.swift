//
//  EVAppIntents.swift
//  EVforME?
//
//  App Intents per Shortcuts / Siri (iOS 17+).
//

import AppIntents
import Foundation

struct SimulateEVIntent: AppIntent {
    static var title: LocalizedStringResource = LocalizedStringResource("intent_simulate_title")
    static var description = IntentDescription(LocalizedStringResource("intent_simulate_description"))

    @Parameter(title: LocalizedStringResource("intent_param_yearly_km_title"), description: LocalizedStringResource("intent_param_yearly_km_description"), default: 12_000)
    var yearlyKm: Int

    @Parameter(title: LocalizedStringResource("intent_param_home_charging_title"), default: true)
    var hasHomeCharging: Bool

    static var openAppWhenRun: Bool = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog & ReturnsValue<String> {
        let outcome = SimulateEVIntentRunner.run(
            yearlyKm: yearlyKm,
            hasHomeCharging: hasHomeCharging
        )
        return .result(value: outcome.message, dialog: IntentDialog(stringLiteral: outcome.message))
    }
}

/// Logica testabile dell’intent: niente starter silent se l’auto salvata è stata rimossa.
enum SimulateEVIntentRunner {
    struct Outcome: Equatable {
        let message: String
        let didSimulate: Bool
    }

    @MainActor
    static func run(yearlyKm: Int, hasHomeCharging: Bool) -> Outcome {
        let clampedKm = max(1000, min(120_000, yearlyKm))
        let saved = StorageService.shared.loadLastUserInput()

        if let saved {
            var input = saved
            input.dailyKm = clampedKm
            input.hasHomeCharging = hasHomeCharging
            // loadLastUserInput already emptied removed ids (no starter). Do not refill.
            guard CatalogVehicleIdResolver.hasResolvableVehiclePair(input),
                  let result = EVSimulator.simulate(input: input) else {
                return Outcome(message: L10n.catalogVehiclePickAnother, didSimulate: false)
            }
            return persistAndSummarize(input: input, result: result)
        }

        // First run (nothing saved): starters are OK.
        var input = UserInput(
            dailyKm: clampedKm,
            hasHomeCharging: hasHomeCharging,
            areaType: .urban,
            fuelPrice: OfficialEnergyCosts.Fallback.petrolPerLiter,
            ownershipYears: 5,
            electricityPricePerKWh: 0.31,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            scenario: .realistic
        )
        guard CatalogVehicleIdResolver.hasResolvableVehiclePair(input),
              let result = EVSimulator.simulate(input: input) else {
            return Outcome(message: L10n.catalogVehiclePickAnother, didSimulate: false)
        }
        return persistAndSummarize(input: input, result: result)
    }

    @MainActor
    private static func persistAndSummarize(input: UserInput, result: SimulationResult) -> Outcome {
        StorageService.shared.saveUserInput(input)
        ScenarioHistoryStore.save(result: result, input: input)
        WidgetSnapshotStore.save(from: result, input: input)

        let sourceName = VehicleCatalogService.shared.vehicle(by: input.sourceVehicleId)?.displayName
            ?? input.sourceVehicleId
        let targetName = VehicleCatalogService.shared.vehicle(by: input.targetVehicleId)?.displayName
            ?? input.targetVehicleId
        let savingsBit: String
        if result.yearlySavingsRange.upperBound > 0 {
            savingsBit = L10n.impactSaveBetween(result.yearlySavingsRange.lowerBound, result.yearlySavingsRange.upperBound)
        } else {
            savingsBit = L10n.impactCurrentCheaper()
        }
        let summary = "\(result.verdict.title). \(sourceName) → \(targetName). \(savingsBit) · \(L10n.impactChargePerWeek(result.weeklyCharges))"
        return Outcome(message: summary, didSimulate: true)
    }
}

struct OpenLastVerdictIntent: AppIntent {
    static var title: LocalizedStringResource = LocalizedStringResource("intent_open_verdict_title")
    static var description = IntentDescription(LocalizedStringResource("intent_open_verdict_description"))
    static var openAppWhenRun: Bool = true

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        AppDeepLink.requestOpenLastVerdict()
        return .result(dialog: IntentDialog(stringLiteral: L10n.openLastVerdictDialog))
    }
}

struct EVforMEAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: SimulateEVIntent(),
            phrases: [
                "Simulate EV with \(.applicationName)",
                "Is an electric car for me in \(.applicationName)",
            ],
            shortTitle: LocalizedStringResource("intent_shortcut_simulate_short"),
            systemImageName: "bolt.car.fill"
        )
        AppShortcut(
            intent: OpenLastVerdictIntent(),
            phrases: [
                "Open last EV verdict in \(.applicationName)",
            ],
            shortTitle: LocalizedStringResource("intent_shortcut_open_short"),
            systemImageName: "checkmark.seal.fill"
        )
    }
}

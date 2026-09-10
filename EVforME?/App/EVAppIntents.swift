//
//  EVAppIntents.swift
//  EVforME?
//
//  App Intents per Shortcuts / Siri (iOS 26–27).
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
        var input = StorageService.shared.loadLastUserInput() ?? UserInput(
            dailyKm: yearlyKm,
            hasHomeCharging: hasHomeCharging,
            areaType: .urban,
            fuelPrice: 1.7,
            ownershipYears: 5,
            electricityPricePerKWh: 0.25,
            sourceVehicleId: Defaults.starterSourceVehicleId,
            targetVehicleId: Defaults.starterTargetVehicleId,
            scenario: .realistic
        )
        input.dailyKm = max(1000, min(120_000, yearlyKm))
        input.hasHomeCharging = hasHomeCharging
        if input.sourceVehicleId.isEmpty {
            input.sourceVehicleId = Defaults.starterSourceVehicleId
        }
        if input.targetVehicleId.isEmpty {
            input.targetVehicleId = Defaults.starterTargetVehicleId
        }

        let result = EVSimulator.simulate(input: input)
        StorageService.shared.saveUserInput(input)
        guard let result else {
            return .result(
                value: L10n.checkInputValues,
                dialog: IntentDialog(stringLiteral: L10n.checkInputValues)
            )
        }
        ScenarioHistoryStore.save(result: result, input: input)
        WidgetSnapshotStore.save(from: result, input: input)

        let summary = "\(result.verdict.title). \(L10n.impactSaveBetween(result.yearlySavingsRange.lowerBound, result.yearlySavingsRange.upperBound)) · \(L10n.impactChargePerWeek(result.weeklyCharges))"
        return .result(value: summary, dialog: IntentDialog(stringLiteral: summary))
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

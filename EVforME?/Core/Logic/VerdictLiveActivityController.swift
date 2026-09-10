//
//  VerdictLiveActivityController.swift
//  EVforME?
//

import ActivityKit
import Foundation

enum VerdictLiveActivityController {
    @MainActor
    static func publish(from result: SimulationResult, input: UserInput) {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }

        let state = VerdictActivityAttributes.ContentState(
            title: result.verdict.title,
            subtitle: result.verdict.description,
            savingsMin: result.yearlySavingsRange.lowerBound,
            savingsMax: result.yearlySavingsRange.upperBound,
            weeklyCharges: result.weeklyCharges,
            breakEvenMonths: result.breakEvenMonths,
            fuelPrice: input.fuelPrice
        )
        let attributes = VerdictActivityAttributes(yearlyKm: input.dailyKm)
        let content = ActivityContent(
            state: state,
            staleDate: Date().addingTimeInterval(8 * 60 * 60)
        )

        // Aggiorna activity esistente, altrimenti ne crea una.
        if let existing = Activity<VerdictActivityAttributes>.activities.first {
            Task { await existing.update(content) }
            return
        }

        do {
            _ = try Activity.request(
                attributes: attributes,
                content: content,
                pushType: nil
            )
        } catch {
            // Live Activity non disponibile (permessi / device) — silenzioso.
        }
    }

    @MainActor
    static func endAll() {
        for activity in Activity<VerdictActivityAttributes>.activities {
            Task {
                await activity.end(nil, dismissalPolicy: .after(.now + 2))
            }
        }
    }
}

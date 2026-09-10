//
//  VerdictExplanationService.swift
//  EVforME?
//
//  Spiegazione on-device del verdetto via Foundation Models (Apple Intelligence).
//

import Foundation
import FoundationModels

enum VerdictExplanationService {
    static var isModelAvailable: Bool {
        if case .available = SystemLanguageModel.default.availability {
            return true
        }
        return false
    }

    /// Testo breve e concreto (2–4 frasi). Fallback locale se il modello non è disponibile.
    static func explain(result: SimulationResult, input: UserInput) async -> String {
        let fallback = fallbackExplanation(result: result, input: input)
        guard isModelAvailable else { return fallback }

        let session = LanguageModelSession(
            instructions: """
            Sei un consulente auto elettriche chiaro e onesto. Rispondi nella stessa lingua \
            dell'utente (italiano o inglese). Massimo 4 frasi corte. Niente markdown, \
            niente elenchi, niente promesse di incentivi. Usa solo i numeri forniti.
            """
        )

        let prompt = """
        Verdetto: \(result.verdict.rawValue) (\(result.verdict.title))
        Km/anno: \(input.dailyKm)
        Ricarica casa: \(input.hasHomeCharging ? "sì" : "no")
        Area: \(input.areaType.rawValue)
        Scenario: \(input.scenario.title)
        Ricariche/settimana stimate: \(result.weeklyCharges)
        Risparmio annuo stimato (€): \(result.yearlySavingsRange.lowerBound)–\(result.yearlySavingsRange.upperBound)
        Motivi: \(result.keyReasons.joined(separator: " | "))
        Spiega perché questo verdetto ha senso per questa persona.
        """

        do {
            let response = try await session.respond(to: prompt)
            let text = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
            return text.isEmpty ? fallback : text
        } catch {
            return fallback
        }
    }

    private static func fallbackExplanation(result: SimulationResult, input: UserInput) -> String {
        let savings = result.yearlySavingsRange
        switch result.verdict {
        case .yes:
            return L10n.verdictAIFallbackYes(input.dailyKm, savings.lowerBound, savings.upperBound, result.weeklyCharges)
        case .maybe:
            return L10n.verdictAIFallbackMaybe(input.dailyKm, savings.lowerBound, savings.upperBound)
        case .notYet:
            return L10n.verdictAIFallbackNotYet(input.dailyKm, result.weeklyCharges)
        }
    }
}

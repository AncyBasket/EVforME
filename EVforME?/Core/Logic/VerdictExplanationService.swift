//
//  VerdictExplanationService.swift
//  EVforME?
//
//  Spiegazione on-device del verdetto via Foundation Models (Apple Intelligence)
//  quando disponibili (iOS 26+). Sotto: solo fallback L10n — zero crash.
//

import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

enum VerdictExplanationService {
    static var isModelAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26, *) {
            if case .available = SystemLanguageModel.default.availability {
                return true
            }
        }
        #endif
        return false
    }

    /// Testo breve e concreto (2–4 frasi). Fallback locale se il modello non è disponibile.
    static func explain(result: SimulationResult, input: UserInput) async -> String {
        let fallback = fallbackExplanation(result: result, input: input)
        guard isModelAvailable else { return fallback }

        #if canImport(FoundationModels)
        if #available(iOS 26, *) {
            return await explainWithFoundationModels(result: result, input: input, fallback: fallback)
        }
        #endif
        return fallback
    }

    #if canImport(FoundationModels)
    @available(iOS 26, *)
    private static func explainWithFoundationModels(
        result: SimulationResult,
        input: UserInput,
        fallback: String
    ) async -> String {
        let session = LanguageModelSession(
            instructions: """
            Sei un consulente auto elettriche chiaro e onesto. Rispondi nella stessa lingua \
            dell'utente (italiano o inglese). Massimo 4 frasi corte. Niente markdown, \
            niente elenchi, niente promesse di incentivi. Spiegazione solo qualitativa: \
            non scrivere cifre, importi in euro, percentuali né km.
            """
        )

        let prompt = """
        Verdetto: \(result.verdict.rawValue) (\(result.verdict.title))
        Ha ricarica a casa: \(input.hasHomeCharging ? "sì" : "no")
        Area: \(input.areaType.rawValue)
        Scenario: \(input.scenario.title)
        Motivi (qualitativi): \(result.keyReasons.joined(separator: " | "))
        Spiega in modo qualitativo perché questo verdetto ha senso. Nessun numero.
        """

        do {
            let response = try await session.respond(to: prompt)
            let text = response.content.trimmingCharacters(in: .whitespacesAndNewlines)
            if text.isEmpty { return fallback }
            if Self.containsDisallowedFigures(text, relativeTo: result, input: input) {
                return fallback
            }
            return text
        } catch {
            return fallback
        }
    }
    #endif

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

    /// Se il modello inventa cifre diverse da quelle calcolate, scarta il testo.
    static func containsDisallowedFigures(
        _ text: String,
        relativeTo result: SimulationResult,
        input: UserInput
    ) -> Bool {
        let allowed = Set(Self.allowedFigureTokens(result: result, input: input))
        let pattern = #"\d+(?:[.,]\d+)?"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return false }
        let ns = text as NSString
        let matches = regex.matches(in: text, range: NSRange(location: 0, length: ns.length))
        for m in matches {
            let token = ns.substring(with: m.range)
                .replacingOccurrences(of: ",", with: ".")
            if !allowed.contains(token) {
                // Qualsiasi cifra non nella allowlist → fallback (prompt chiede zero numeri).
                return true
            }
        }
        // Prompt qualitativo: anche cifre “ammesse” fanno scattare il fallback.
        return !matches.isEmpty
    }

    private static func allowedFigureTokens(result: SimulationResult, input: UserInput) -> [String] {
        var tokens: [String] = [
            "\(input.dailyKm)",
            "\(result.weeklyCharges)",
            "\(result.yearlySavingsRange.lowerBound)",
            "\(result.yearlySavingsRange.upperBound)",
            "\(abs(result.yearlySavingsRange.lowerBound))",
            "\(abs(result.yearlySavingsRange.upperBound))"
        ]
        return tokens
    }
}

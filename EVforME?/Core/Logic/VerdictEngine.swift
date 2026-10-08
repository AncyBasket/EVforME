//
//  VerdictEngine.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

struct VerdictEngine {

    /// Verdetto solo su costi di gestione (energia + bollo + manutenzione + RC).
    /// Il premium di listino non decide mai sì/no — resta eventuale nota “se compro” a parte.
    /// - Parameters:
    ///   - netPurchasePremiumEUR: ignorato per il verdetto (compat API / call site).
    ///   - comparisonIntent: ignorato per le soglie (sempre opex-only).
    static func evaluate(
        result: EVSimulationResult,
        scenario: Scenario,
        netPurchasePremiumEUR: Double = 0,
        ownershipYears: Int = 5,
        comparisonIntent: ComparisonIntent = .alreadyOwned
    ) -> EVVerdict {
        _ = netPurchasePremiumEUR
        _ = ownershipYears
        _ = comparisonIntent

        let savings = result.totalSavings
        let yearlyDelta = result.yearlyIceCost - result.yearlyEvCost

        // Soglie gestione: vantaggio annuale chiaro sull’orizzonte simulato.
        let savingsThreshold: Double
        let deltaThreshold: Double
        switch scenario {
        case .optimistic:
            savingsThreshold = 1_500
            deltaThreshold = 250
        case .realistic:
            savingsThreshold = 2_000
            deltaThreshold = 350
        case .pessimistic:
            savingsThreshold = 2_500
            deltaThreshold = 450
        }

        let clearOpexWin = yearlyDelta > deltaThreshold && savings > savingsThreshold
        if clearOpexWin {
            return .yes
        }
        if yearlyDelta > 0, savings > 0 {
            return .maybe
        }
        return .notYet
    }
}

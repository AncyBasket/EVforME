//
//  VerdictEngine.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

struct VerdictEngine {

    /// Valuta il verdetto su opex e, in modalità acquisto, sul recupero del premium di listino.
    /// - `netPurchasePremiumEUR == 0` (già possedute / opex only): il sì/no non dipende dal delta listino.
    static func evaluate(
        result: EVSimulationResult,
        scenario: Scenario,
        netPurchasePremiumEUR: Double = 0,
        ownershipYears: Int = 5,
        comparisonIntent: ComparisonIntent = .consideringPurchase
    ) -> EVVerdict {

        let savings = result.totalSavings
        let yearlyDelta = result.yearlyIceCost - result.yearlyEvCost
        let horizonMonths = max(1, ownershipYears) * 12
        let opexOnly = comparisonIntent == .alreadyOwned || netPurchasePremiumEUR <= 0

        let monthsToPayback: Int?
        if yearlyDelta > 50, netPurchasePremiumEUR > 0 {
            monthsToPayback = max(1, Int(ceil(netPurchasePremiumEUR / yearlyDelta * 12.0)))
        } else if yearlyDelta > 50 {
            monthsToPayback = 1
        } else {
            monthsToPayback = nil
        }
        let paysBackInHorizon = opexOnly
            ? (yearlyDelta > 50)
            : (monthsToPayback.map { $0 <= horizonMonths } ?? false)

        // Soglie: in opex-only basta un vantaggio gestionale chiaro (soglia totale più bassa).
        let savingsThreshold: Double
        let deltaThreshold: Double
        switch scenario {
        case .optimistic:
            savingsThreshold = opexOnly ? 1_500 : 3_000
            deltaThreshold = opexOnly ? 250 : 500
        case .realistic:
            savingsThreshold = opexOnly ? 2_000 : 5_000
            deltaThreshold = opexOnly ? 350 : 600
        case .pessimistic:
            savingsThreshold = opexOnly ? 2_500 : 7_000
            deltaThreshold = opexOnly ? 450 : 800
        }

        if savings > savingsThreshold, yearlyDelta > deltaThreshold, paysBackInHorizon {
            return .yes
        }
        if yearlyDelta > 0, savings > 0 {
            return .maybe
        }
        return .notYet
    }
}

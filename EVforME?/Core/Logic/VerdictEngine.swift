//
//  VerdictEngine.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

struct VerdictEngine {

    /// Valuta il verdetto su opex **e** recupero del premium di listino entro l'orizzonte di possesso.
    static func evaluate(
        result: EVSimulationResult,
        scenario: Scenario,
        netPurchasePremiumEUR: Double = 0,
        ownershipYears: Int = 5
    ) -> EVVerdict {

        let savings = result.totalSavings
        let yearlyDelta = result.yearlyIceCost - result.yearlyEvCost
        let horizonMonths = max(1, ownershipYears) * 12

        let monthsToPayback: Int?
        if yearlyDelta > 50, netPurchasePremiumEUR > 0 {
            monthsToPayback = max(1, Int(ceil(netPurchasePremiumEUR / yearlyDelta * 12.0)))
        } else if yearlyDelta > 50 {
            monthsToPayback = 1
        } else {
            monthsToPayback = nil
        }
        let paysBackInHorizon = monthsToPayback.map { $0 <= horizonMonths } ?? false

        let savingsThreshold: Double
        let deltaThreshold: Double
        switch scenario {
        case .optimistic:
            savingsThreshold = 3_000
            deltaThreshold = 500
        case .realistic:
            savingsThreshold = 5_000
            deltaThreshold = 600
        case .pessimistic:
            savingsThreshold = 7_000
            deltaThreshold = 800
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

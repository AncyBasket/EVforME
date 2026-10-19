//
//  Scenario.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

enum Scenario: Double, CaseIterable, Identifiable {
    case pessimistic = 0.8
    case realistic   = 1.0
    case optimistic  = 1.2

    var id: Self { self }

    var title: String {
        switch self {
        case .pessimistic: return L10n.scenarioPessimistic
        case .realistic:   return L10n.scenarioRealistic
        case .optimistic:  return L10n.scenarioOptimistic
        }
    }
    
    var scenarioDescription: String {
        switch self {
        case .pessimistic: return L10n.scenarioDescriptionPessimistic
        case .realistic:   return L10n.scenarioDescriptionRealistic
        case .optimistic:  return L10n.scenarioDescriptionOptimistic
        }
    }
    
    /// Timeline fissa rimossa: prometteva risparmi anche con verdetto negativo.
    /// `TimeEvolutionView` deriva le righe dai costi cumulati quando disponibili.
    var timelineText: [String] { [] }

    /// Tre punti derivati dai costi cumulati (anno 1, metà, fine orizzonte).
    static func derivedTimeline(from comparison: [YearlyComparison]) -> [String] {
        guard let first = comparison.first, let last = comparison.last else { return [] }
        let mid = comparison[comparison.count / 2]
        return [first, mid, last].map { year in
            let delta = year.gasCost - year.evCost
            if delta > 50 {
                return L10n.timelineDerivedEvAhead(year.year, Int(delta.rounded()))
            }
            if delta < -50 {
                return L10n.timelineDerivedCurrentAhead(year.year, Int((-delta).rounded()))
            }
            return L10n.timelineDerivedClose(year.year)
        }
    }

    /// Moltiplicatore dei costi ICE
    var iceCostMultiplier: Double {
        switch self {
        case .pessimistic: return 0.9
        case .realistic:   return 1.0
        case .optimistic:  return 1.1
        }
    }

    /// Moltiplicatore dei costi EV
    var evCostMultiplier: Double {
        switch self {
        case .pessimistic: return 1.1
        case .realistic:   return 1.0
        case .optimistic:  return 0.9
        }
    }
}

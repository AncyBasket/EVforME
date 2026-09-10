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
    
    var timelineText: [String] {
        switch self {
        case .pessimistic: return [
            L10n.timelinePessimistic1,
            L10n.timelinePessimistic2,
            L10n.timelinePessimistic3
        ]
        case .realistic: return [
            L10n.timelineRealistic1,
            L10n.timelineRealistic2,
            L10n.timelineRealistic3
        ]
        case .optimistic: return [
            L10n.timelineOptimistic1,
            L10n.timelineOptimistic2,
            L10n.timelineOptimistic3
        ]
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

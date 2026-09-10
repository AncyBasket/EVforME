//
//  SimulationResult.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

/// Verdict on EV suitability for the user
enum EVVerdict: String {
    case yes = "yes"
    case maybe = "maybe"
    case notYet = "notYet"
    
    var emoji: String {
        switch self {
        case .yes: return "✅"
        case .maybe: return "🤔"
        case .notYet: return "⏳"
        }
    }
    
    var title: String {
        switch self {
        case .yes: return L10n.verdictYesTitle
        case .maybe: return L10n.verdictMaybeTitle
        case .notYet: return L10n.verdictNotYetTitle
        }
    }
    
    var description: String {
        switch self {
        case .yes: return L10n.verdictYesDescription
        case .maybe: return L10n.verdictMaybeDescription
        case .notYet: return L10n.verdictNotYetDescription
        }
    }
}

/// Result of EV simulation containing verdict, costs, and recommendations
struct SimulationResult {
    /// Overall verdict on EV suitability
    let verdict: EVVerdict
    
    /// Estimated number of charges needed per week
    let weeklyCharges: Int
    
    /// Estimated yearly savings range compared to gas car (in local currency)
    let yearlySavingsRange: ClosedRange<Int>

    /// Mesi stimati per recuperare il premium di listino netto con il risparmio operativo. `nil` se non conviene.
    let breakEvenMonths: Int?
    
    /// Key reasons explaining the verdict
    let keyReasons: [String]
    
    /// Personalized fear vs reality items addressing common concerns
    let fearReality: [FearRealityItem]
    
    /// Year-by-year cumulative opex comparison across ownership horizon
    let yearlyComparison: [YearlyComparison]

    /// Spezzatino opex annuo veicolo attuale (allineato al motore).
    let sourceYearlyBreakdown: OperatingCostBreakdown

    /// Spezzatino opex annuo veicolo elettrificato (allineato al motore).
    let targetYearlyBreakdown: OperatingCostBreakdown
}

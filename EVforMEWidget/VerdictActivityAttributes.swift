//
//  VerdictActivityAttributes.swift
//  EVforMEWidget
//
//  Deve restare allineato con l’app (ActivityKit encoding).
//

import ActivityKit
import Foundation

struct VerdictActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var title: String
        var subtitle: String
        var savingsMin: Int
        var savingsMax: Int
        var weeklyCharges: Int
        var breakEvenMonths: Int?
        var fuelPrice: Double
    }

    var yearlyKm: Int
}

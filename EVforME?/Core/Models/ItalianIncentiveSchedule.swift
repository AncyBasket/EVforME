//
//  ItalianIncentiveSchedule.swift
//  EVforME?
//
//  Schema incentivi IT caricabile da JSON (bundle / cache / remoto).
//

import Foundation

nonisolated struct ItalianIncentiveBracket: Codable, Equatable, Sendable {
    let maxPriceEUR: Double
    let bonusEUR: Double
}

nonisolated struct ItalianIncentiveSchedule: Codable, Equatable, Sendable {
    let country: String
    let currency: String
    let updatedAt: String?
    let maxListPriceEUR: Double
    let maxBonusEUR: Double
    let scrappageExtraEUR: Double
    let scrappageMaxReplacingPriceEUR: Double
    let brackets: [ItalianIncentiveBracket]
    let sourceNote: String?

    static let bundledFallback = ItalianIncentiveSchedule(
        country: "IT",
        currency: "EUR",
        updatedAt: nil,
        maxListPriceEUR: 45_000,
        maxBonusEUR: 7_000,
        scrappageExtraEUR: 2_000,
        scrappageMaxReplacingPriceEUR: 18_000,
        brackets: [
            ItalianIncentiveBracket(maxPriceEUR: 30_000, bonusEUR: 5_000),
            ItalianIncentiveBracket(maxPriceEUR: 35_000, bonusEUR: 4_000),
            ItalianIncentiveBracket(maxPriceEUR: 42_000, bonusEUR: 2_500),
            ItalianIncentiveBracket(maxPriceEUR: 45_000, bonusEUR: 1_500),
        ],
        sourceNote: nil
    )

    func estimatedPurchaseBonusEUR(
        evListPrice: Double,
        replacingVehiclePrice: Double,
        hasHomeCharging: Bool
    ) -> Double {
        guard evListPrice > 0, evListPrice <= maxListPriceEUR else { return 0 }

        let sorted = brackets.sorted { $0.maxPriceEUR < $1.maxPriceEUR }
        var bonus: Double = sorted.last?.bonusEUR ?? 0
        for bracket in sorted {
            if evListPrice <= bracket.maxPriceEUR {
                bonus = bracket.bonusEUR
                break
            }
        }

        if replacingVehiclePrice > 0, replacingVehiclePrice <= scrappageMaxReplacingPriceEUR {
            bonus += scrappageExtraEUR
        }

        // Reserved for future wallbox schemes.
        _ = hasHomeCharging

        return min(bonus, maxBonusEUR)
    }
}

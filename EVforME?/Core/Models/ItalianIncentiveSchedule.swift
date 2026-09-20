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

enum IncentiveWindowStatus: Equatable, Sendable {
    case unknown
    case active(until: Date?)
    case expired(on: Date)
    case notYetStarted(from: Date)
}

nonisolated struct ItalianIncentiveSchedule: Codable, Equatable, Sendable {
    let country: String
    let currency: String
    let updatedAt: String?
    /// ISO date (yyyy-MM-dd) o datetime — opzionale, retrocompatibile.
    let validFrom: String?
    let validUntil: String?
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
        validFrom: nil,
        validUntil: nil,
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

        _ = hasHomeCharging

        return min(bonus, maxBonusEUR)
    }

    var validFromDate: Date? { Self.parseFlexibleDate(validFrom) }
    var validUntilDate: Date? { Self.parseFlexibleDate(validUntil) }

    func windowStatus(asOf date: Date = Date()) -> IncentiveWindowStatus {
        let calendar = Calendar.current
        if let from = validFromDate, date < calendar.startOfDay(for: from) {
            return .notYetStarted(from: from)
        }
        if let until = validUntilDate {
            let startOfUntil = calendar.startOfDay(for: until)
            guard let dayAfterUntil = calendar.date(byAdding: .day, value: 1, to: startOfUntil) else {
                return .active(until: until)
            }
            if date >= dayAfterUntil {
                return .expired(on: until)
            }
            return .active(until: until)
        }
        if validFrom == nil && validUntil == nil {
            return .unknown
        }
        return .active(until: nil)
    }

    var isSchedulePossiblyStale: Bool {
        if case .expired = windowStatus() { return true }
        return false
    }

    static func parseFlexibleDate(_ raw: String?) -> Date? {
        guard let raw, !raw.isEmpty else { return nil }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        if let d = iso.date(from: String(raw.prefix(10))) {
            return d
        }
        let full = ISO8601DateFormatter()
        full.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = full.date(from: raw) { return d }
        full.formatOptions = [.withInternetDateTime]
        return full.date(from: raw)
    }
}

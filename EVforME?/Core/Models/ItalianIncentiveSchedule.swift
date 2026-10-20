//
//  ItalianIncentiveSchedule.swift
//  EVforME?
//
//  Schema incentivi IT caricabile da JSON (bundle / cache / remoto).
//

import Foundation

nonisolated struct ItalianIncentiveBracket: Codable, Equatable, Sendable {
    /// Soglia ISEE massima (€) per questo importo. Preferita rispetto a `maxPriceEUR`.
    let maxISEEEUR: Double?
    /// Legacy: soglia listino (JSON vecchi).
    let maxPriceEUR: Double?
    let bonusEUR: Double

    init(maxISEEEUR: Double? = nil, maxPriceEUR: Double? = nil, bonusEUR: Double) {
        self.maxISEEEUR = maxISEEEUR
        self.maxPriceEUR = maxPriceEUR
        self.bonusEUR = bonusEUR
    }
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
    /// ISO date — opzionale; omesso se senza fonte (audit).
    let validFrom: String?
    let validUntil: String?
    /// Tetto listino: di default IVA esclusa (vedi `maxListPriceIsExVAT`).
    let maxListPriceEUR: Double
    let maxListPriceIsExVAT: Bool?
    let maxBonusEUR: Double
    let scrappageExtraEUR: Double
    let scrappageMaxReplacingPriceEUR: Double
    let brackets: [ItalianIncentiveBracket]
    let sourceNote: String?

    static let italianVATDivisor: Double = 1.22

    static let bundledFallback = ItalianIncentiveSchedule(
        country: "IT",
        currency: "EUR",
        updatedAt: nil,
        validFrom: nil,
        validUntil: "2026-06-30",
        maxListPriceEUR: 35_000,
        maxListPriceIsExVAT: true,
        maxBonusEUR: 11_000,
        scrappageExtraEUR: 0,
        scrappageMaxReplacingPriceEUR: 0,
        brackets: [
            ItalianIncentiveBracket(maxISEEEUR: 30_000, bonusEUR: 11_000),
            ItalianIncentiveBracket(maxISEEEUR: 40_000, bonusEUR: 9_000),
        ],
        sourceNote: "Bonus MASE 2025 chiuso"
    )

    /// - Parameters:
    ///   - evListPrice: listino IVA inclusa (€).
    ///   - iseeEUR: ISEE dichiarato; senza ISEE valido → 0 (non inventiamo la fascia).
    func estimatedPurchaseBonusEUR(
        evListPrice: Double,
        replacingVehiclePrice: Double,
        hasHomeCharging: Bool,
        iseeEUR: Double? = nil,
        asOf date: Date = Date()
    ) -> Double {
        // Finestra chiusa / scaduta → mai applicare l’incentivo ai calcoli.
        if case .expired = windowStatus(asOf: date) { return 0 }
        if case .notYetStarted = windowStatus(asOf: date) { return 0 }
        if case .unknown = windowStatus(asOf: date) { return 0 }

        guard evListPrice > 0 else { return 0 }
        let exVAT = (maxListPriceIsExVAT ?? true) ? (evListPrice / Self.italianVATDivisor) : evListPrice
        guard exVAT <= maxListPriceEUR else { return 0 }

        let iseeBrackets = brackets.compactMap { b -> (Double, Double)? in
            guard let cap = b.maxISEEEUR else { return nil }
            return (cap, b.bonusEUR)
        }.sorted { $0.0 < $1.0 }

        var bonus: Double = 0
        if !iseeBrackets.isEmpty {
            guard let isee = iseeEUR, isee > 0, isee <= 40_000 else { return 0 }
            for (cap, amount) in iseeBrackets {
                if isee <= cap {
                    bonus = amount
                    break
                }
            }
        } else {
            // Legacy price brackets (JSON vecchi / test).
            let sorted = brackets.compactMap { b -> (Double, Double)? in
                guard let cap = b.maxPriceEUR else { return nil }
                return (cap, b.bonusEUR)
            }.sorted { $0.0 < $1.0 }
            bonus = sorted.last?.1 ?? 0
            for (cap, amount) in sorted {
                if evListPrice <= cap {
                    bonus = amount
                    break
                }
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

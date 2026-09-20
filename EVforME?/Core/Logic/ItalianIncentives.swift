//
//  ItalianIncentives.swift
//  EVforME?
//
//  Stime semplificate stile ecobonus IT — non è consulenza fiscale/legale.
//  I bracket vivono in `italian_incentives.json` (+ cache/remoto via ItalianIncentivesService).
//

import Foundation

nonisolated enum ItalianIncentives {
    /// Nota trasparenza fonti / ipotesi.
    static var transparencyNote: String { L10n.incentivesTransparencyNote }

    /// Schedule attivo (dopo refresh a launch/foreground).
    static var schedule: ItalianIncentiveSchedule {
        ItalianIncentivesService.shared.currentSchedule
    }

    static var windowStatus: IncentiveWindowStatus {
        schedule.windowStatus()
    }

    /// Copy UI per la finestra incentivo.
    static var windowBadgeText: String {
        switch windowStatus {
        case .unknown:
            return L10n.incentiveWindowVerifyOfficial
        case .active(let until):
            if let until {
                return L10n.incentiveWindowBuyBy(Self.displayDate(until))
            }
            return L10n.incentiveWindowOpenNoEnd
        case .expired:
            return L10n.incentiveWindowPossiblyStale
        case .notYetStarted(let from):
            return L10n.incentiveWindowStarts(Self.displayDate(from))
        }
    }

    private static func displayDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "it_IT")
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }

    /// Bonus acquisto stimato (€) in base a listino EV e auto sostituita.
    static func estimatedPurchaseBonusEUR(
        evListPrice: Double,
        replacingVehiclePrice: Double,
        hasHomeCharging: Bool
    ) -> Double {
        schedule.estimatedPurchaseBonusEUR(
            evListPrice: evListPrice,
            replacingVehiclePrice: replacingVehiclePrice,
            hasHomeCharging: hasHomeCharging
        )
    }

    /// Alias usato storicamente nei calcoli “tipici”.
    static var typicalPurchaseBonusEUR: Double {
        estimatedPurchaseBonusEUR(
            evListPrice: 32_000,
            replacingVehiclePrice: 12_000,
            hasHomeCharging: true
        )
    }
}

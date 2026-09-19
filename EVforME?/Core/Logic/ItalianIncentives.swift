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

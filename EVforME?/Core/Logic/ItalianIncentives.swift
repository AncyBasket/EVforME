//
//  ItalianIncentives.swift
//  EVforME?
//
//  Stime semplificate stile ecobonus IT — non è consulenza fiscale/legale.
//

import Foundation

enum ItalianIncentives {
    /// Nota trasparenza fonti / ipotesi.
    static var transparencyNote: String { L10n.incentivesTransparencyNote }

    /// Bonus acquisto stimato (€) in base a listino EV e auto sostituita.
    static func estimatedPurchaseBonusEUR(
        evListPrice: Double,
        replacingVehiclePrice: Double,
        hasHomeCharging: Bool
    ) -> Double {
        // Molti schemi storici escludevano EV oltre una soglia di listino.
        guard evListPrice > 0, evListPrice <= 45_000 else { return 0 }

        var bonus: Double
        switch evListPrice {
        case ...30_000:
            bonus = 5_000
        case ...35_000:
            bonus = 4_000
        case ...42_000:
            bonus = 2_500
        default:
            bonus = 1_500
        }

        // Proxy rottamazione: auto attuale di valore contenuto.
        if replacingVehiclePrice > 0, replacingVehiclePrice <= 18_000 {
            bonus += 2_000
        }

        // `hasHomeCharging` reserved for future wallbox schemes — non gonfia il bonus numerico.
        _ = hasHomeCharging

        return min(bonus, 7_000)
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

//
//  OfficialLinks.swift
//  EVforME?
//
//  URL pubblici hardcoded usati in UI. Aggiornare qui (e nei test hygiene).
//

import Foundation

enum OfficialLinks {
    /// Portale MASE / PNRR Bonus Veicoli Elettrici (ISEE + rottamazione). Verificato ott 2026.
    static let italianVehicleIncentives = URL(string: "https://www.bonusveicolielettrici.mase.gov.it/index.html")!

    /// Ecobonus MIMIT / Invitalia (tabelle contributi storiche).
    static let mimitEcobonusContributi = URL(string: "https://ecobonus.mimit.gov.it/index.php/contributi")!

    /// Tutti gli URL https da verificare nei test.
    static var allHTTPSLinks: [URL] {
        [
            italianVehicleIncentives,
            mimitEcobonusContributi,
            URL(string: Defaults.mimitFuelPricesCSVURL)!,
            URL(string: Defaults.eurostatElectricityURL)!,
            URL(string: "https://www.automobiledimension.com/car-comparison.php")!,
        ]
    }
}

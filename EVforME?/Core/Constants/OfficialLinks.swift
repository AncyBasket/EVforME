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

    /// Dataset EEA CO₂ cars (fonte catalogo WLTP / fill da co2cars).
    static let eeaCO2CarsDataset = URL(string: "https://www.eea.europa.eu/data-and-maps/data/co2-cars-emission-22")!

    /// EPA Fuel Economy (fonte consumi USA in catalogo).
    static let epaFuelEconomy = URL(string: "https://www.fueleconomy.gov/")!

    /// Tutti gli URL https da verificare nei test.
    static var allHTTPSLinks: [URL] {
        [
            italianVehicleIncentives,
            mimitEcobonusContributi,
            eeaCO2CarsDataset,
            epaFuelEconomy,
            FuelFromCO2Constants.eurLexRegulationURL,
            URL(string: Defaults.mimitFuelPricesCSVURL)!,
            URL(string: Defaults.eurostatElectricityURL)!,
            URL(string: "https://www.automobiledimension.com/car-comparison.php")!,
        ]
    }
}

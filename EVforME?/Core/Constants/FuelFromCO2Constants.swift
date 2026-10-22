//
//  FuelFromCO2Constants.swift
//  EVforME?
//
//  Stessa conversione CO₂→L/100 usata in scripts/fill_catalog_fuels_from_eea.py
//  (Reg. (UE) 2017/1151 Allegato XXI, Sub-allegato 7, HC=CO=0).
//

import Foundation

enum FuelFromCO2Constants {
    /// Densità / coefficienti come nello script Python di fill catalogo.
    static let cPetrol = 0.1206
    static let cDiesel = 0.1165
    static let dPetrolKgPerL = 0.745
    static let dDieselKgPerL = 0.834
    static let co2Factor = 0.273

    /// g CO₂/km ÷ questo valore ≈ L/100 km (benzina E10, ≈22.63).
    static var petrolCO2PerL100: Double { dPetrolKgPerL / (cPetrol * co2Factor) }

    /// g CO₂/km ÷ questo valore ≈ L/100 km (diesel B7, ≈26.22; script comment ≈26.25).
    static var dieselCO2PerL100: Double { dDieselKgPerL / (cDiesel * co2Factor) }

    static let eurLexRegulationURL = URL(
        string: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32017R1151"
    )!

    static func litersPer100km(fromCO2GramsPerKm co2: Double, fuelKind: FuelKind) -> Double? {
        guard co2 > 0 else { return nil }
        switch fuelKind {
        case .petrol, .unknown, .lpg, .cng:
            return co2 / petrolCO2PerL100
        case .diesel:
            return co2 / dieselCO2PerL100
        }
    }
}

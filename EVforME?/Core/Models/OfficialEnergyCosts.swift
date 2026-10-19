import Foundation

struct OfficialEnergyCosts: Codable {
    let country: String
    let currency: String
    /// Mediana MIMIT benzina self-service (€/L).
    let fuelPricePerLiter: Double
    /// Mediana MIMIT gasolio self-service (€/L). Assente nei JSON vecchi → fallback.
    let dieselPricePerLiter: Double?
    /// Mediana MIMIT GPL self-service (€/L).
    let lpgPricePerLiter: Double?
    /// Mediana MIMIT metano self-service (€/kg).
    let cngPricePerKg: Double?
    let electricityPricePerKWh: Double
    let updatedAt: String?
    /// Periodo Eurostat (es. `2026-S1`) per la fascia 2.500–4.999 kWh.
    let electricityPeriod: String?

    enum CodingKeys: String, CodingKey {
        case country, currency, fuelPricePerLiter, dieselPricePerLiter
        case lpgPricePerLiter, cngPricePerKg, electricityPricePerKWh, updatedAt
        case electricityPeriod
    }

    init(
        country: String,
        currency: String,
        fuelPricePerLiter: Double,
        dieselPricePerLiter: Double? = nil,
        lpgPricePerLiter: Double? = nil,
        cngPricePerKg: Double? = nil,
        electricityPricePerKWh: Double,
        updatedAt: String?,
        electricityPeriod: String? = nil
    ) {
        self.country = country
        self.currency = currency
        self.fuelPricePerLiter = fuelPricePerLiter
        self.dieselPricePerLiter = dieselPricePerLiter
        self.lpgPricePerLiter = lpgPricePerLiter
        self.cngPricePerKg = cngPricePerKg
        self.electricityPricePerKWh = electricityPricePerKWh
        self.updatedAt = updatedAt
        self.electricityPeriod = electricityPeriod
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        country = try c.decode(String.self, forKey: .country)
        currency = try c.decode(String.self, forKey: .currency)
        fuelPricePerLiter = try c.decode(Double.self, forKey: .fuelPricePerLiter)
        dieselPricePerLiter = try c.decodeIfPresent(Double.self, forKey: .dieselPricePerLiter)
        lpgPricePerLiter = try c.decodeIfPresent(Double.self, forKey: .lpgPricePerLiter)
        cngPricePerKg = try c.decodeIfPresent(Double.self, forKey: .cngPricePerKg)
        electricityPricePerKWh = try c.decode(Double.self, forKey: .electricityPricePerKWh)
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt)
        electricityPeriod = try c.decodeIfPresent(String.self, forKey: .electricityPeriod)
    }

    /// Prezzo unitario allineato al carburante del veicolo attuale (€/L o €/kg per CNG).
    /// Ripieghi MIMIT 19/10/2026 (audit) — non derivare gasolio/GPL dalla benzina.
    enum Fallback {
        static let petrolPerLiter: Double = 2.03
        static let dieselPerLiter: Double = 2.25
        static let lpgPerLiter: Double = 0.77
        static let cngPerKg: Double = 1.95
    }

    func pricePerLiter(for fuelKind: FuelKind) -> Double {
        switch fuelKind {
        case .diesel:
            return dieselPricePerLiter ?? Fallback.dieselPerLiter
        case .lpg:
            return lpgPricePerLiter ?? Fallback.lpgPerLiter
        case .cng:
            return cngPricePerKg ?? Fallback.cngPerKg
        case .petrol, .unknown:
            return fuelPricePerLiter > 0 ? fuelPricePerLiter : Fallback.petrolPerLiter
        }
    }
}

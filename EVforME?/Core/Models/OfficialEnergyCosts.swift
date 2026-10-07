import Foundation

struct OfficialEnergyCosts: Codable {
    let country: String
    let currency: String
    /// Mediana MIMIT benzina self-service (€/L).
    let fuelPricePerLiter: Double
    /// Mediana MIMIT gasolio self-service (€/L). Assente nei JSON vecchi → fallback.
    let dieselPricePerLiter: Double?
    let electricityPricePerKWh: Double
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case country, currency, fuelPricePerLiter, dieselPricePerLiter, electricityPricePerKWh, updatedAt
    }

    init(
        country: String,
        currency: String,
        fuelPricePerLiter: Double,
        dieselPricePerLiter: Double? = nil,
        electricityPricePerKWh: Double,
        updatedAt: String?
    ) {
        self.country = country
        self.currency = currency
        self.fuelPricePerLiter = fuelPricePerLiter
        self.dieselPricePerLiter = dieselPricePerLiter
        self.electricityPricePerKWh = electricityPricePerKWh
        self.updatedAt = updatedAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        country = try c.decode(String.self, forKey: .country)
        currency = try c.decode(String.self, forKey: .currency)
        fuelPricePerLiter = try c.decode(Double.self, forKey: .fuelPricePerLiter)
        dieselPricePerLiter = try c.decodeIfPresent(Double.self, forKey: .dieselPricePerLiter)
        electricityPricePerKWh = try c.decode(Double.self, forKey: .electricityPricePerKWh)
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt)
    }

    /// Prezzo €/L allineato al carburante del veicolo attuale.
    func pricePerLiter(for fuelKind: FuelKind) -> Double {
        switch fuelKind {
        case .diesel:
            if let dieselPricePerLiter { return dieselPricePerLiter }
            // Gasolio IT tipicamente un filo sotto la benzina se manca il dato.
            return (fuelPricePerLiter * 0.97 * 1000).rounded() / 1000
        case .petrol, .unknown:
            return fuelPricePerLiter
        }
    }
}

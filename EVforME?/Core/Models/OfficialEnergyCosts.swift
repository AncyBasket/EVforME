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

    enum CodingKeys: String, CodingKey {
        case country, currency, fuelPricePerLiter, dieselPricePerLiter
        case lpgPricePerLiter, cngPricePerKg, electricityPricePerKWh, updatedAt
    }

    init(
        country: String,
        currency: String,
        fuelPricePerLiter: Double,
        dieselPricePerLiter: Double? = nil,
        lpgPricePerLiter: Double? = nil,
        cngPricePerKg: Double? = nil,
        electricityPricePerKWh: Double,
        updatedAt: String?
    ) {
        self.country = country
        self.currency = currency
        self.fuelPricePerLiter = fuelPricePerLiter
        self.dieselPricePerLiter = dieselPricePerLiter
        self.lpgPricePerLiter = lpgPricePerLiter
        self.cngPricePerKg = cngPricePerKg
        self.electricityPricePerKWh = electricityPricePerKWh
        self.updatedAt = updatedAt
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
    }

    /// Prezzo unitario allineato al carburante del veicolo attuale (€/L o €/kg per CNG).
    func pricePerLiter(for fuelKind: FuelKind) -> Double {
        switch fuelKind {
        case .diesel:
            if let dieselPricePerLiter { return dieselPricePerLiter }
            return (fuelPricePerLiter * 0.97 * 1000).rounded() / 1000
        case .lpg:
            if let lpgPricePerLiter { return lpgPricePerLiter }
            // GPL IT tipicamente ~45–55% della benzina.
            return (fuelPricePerLiter * 0.50 * 1000).rounded() / 1000
        case .cng:
            if let cngPricePerKg { return cngPricePerKg }
            // Metano IT ordine di grandezza ~1,2–1,4 €/kg (fallback statico).
            return 1.28
        case .petrol, .unknown:
            return fuelPricePerLiter
        }
    }
}

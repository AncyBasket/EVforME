import Foundation

struct OfficialEnergyCosts: Codable {
    let country: String
    let currency: String
    let fuelPricePerLiter: Double
    let electricityPricePerKWh: Double
    let updatedAt: String?
}


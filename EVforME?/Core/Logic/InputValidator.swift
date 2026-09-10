//
//  InputValidator.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

/// Validates user input for EV simulation
struct InputValidator {
    
    /// Validates yearly kilometers input
    /// - Parameter km: Yearly kilometers
    /// - Returns: Validation result with error message if invalid
    static func validateDailyKm(_ km: Int) -> ValidationResult {
        if km < 1000 {
            return .invalid(L10n.validationMinKm)
        }
        if km > 120000 {
            return .invalid(L10n.validationMaxKm)
        }
        return .valid
    }
    
    /// Validates fuel price input
    /// - Parameter price: Fuel price per liter
    /// - Returns: Validation result with error message if invalid
    static func validateFuelPrice(_ price: Double) -> ValidationResult {
        if price <= 0 {
            return .invalid(L10n.validationFuelPositive)
        }
        if price > 3.0 {
            return .invalid(L10n.validationFuelHigh)
        }
        return .valid
    }

    /// Prezzo energia €/kWh (domestico o stima ricarica pubblica).
    static func validateElectricityPricePerKWh(_ price: Double) -> ValidationResult {
        if price <= 0 {
            return .invalid(L10n.validationElectricityPositive)
        }
        if price > 2.0 {
            return .invalid(L10n.validationElectricityHigh)
        }
        return .valid
    }
    
    /// Validates ownership years
    /// - Parameter years: Years of ownership
    /// - Returns: Validation result with error message if invalid
    static func validateOwnershipYears(_ years: Int) -> ValidationResult {
        if years < 1 {
            return .invalid(L10n.validationMinYears)
        }
        if years > 20 {
            return .invalid(L10n.validationMaxYears)
        }
        return .valid
    }

    /// Validates source vehicle selection
    static func validateSourceVehicle(_ vehicleId: String) -> ValidationResult {
        if vehicleId.isEmpty {
            return .invalid(L10n.validationSourceVehicleRequired)
        }
        return .valid
    }

    /// Validates target EV selection
    static func validateTargetVehicle(_ vehicleId: String) -> ValidationResult {
        if vehicleId.isEmpty {
            return .invalid(L10n.validationTargetVehicleRequired)
        }
        return .valid
    }
    
    /// Checks if yearly kilometers are valid (convenience method)
    /// - Parameter km: Yearly kilometers
    /// - Returns: true if valid, false otherwise
    static func isDailyKmValid(_ km: Int) -> Bool {
        if case .valid = validateDailyKm(km) {
            return true
        }
        return false
    }
    
    /// Checks if ownership years are valid (convenience method)
    /// - Parameter years: Years of ownership
    /// - Returns: true if valid, false otherwise
    static func isYearsValid(_ years: Int) -> Bool {
        if case .valid = validateOwnershipYears(years) {
            return true
        }
        return false
    }
    
    /// Validates purchase price (€).
    static func validatePurchasePrice(_ price: Double, label: String) -> ValidationResult {
        if price < 1_000 {
            return .invalid(String(format: L10n.validationPurchaseTooLow, label))
        }
        if price > 150_000 {
            return .invalid(String(format: L10n.validationPurchaseTooHigh, label))
        }
        return .valid
    }

    /// Validates entire user input
    /// - Parameter input: User input to validate
    /// - Returns: Array of validation errors (empty if valid)
    static func validate(_ input: UserInput) -> [String] {
        var errors: [String] = []
        
        let kmResult = validateDailyKm(input.dailyKm)
        if case .invalid(let message) = kmResult {
            errors.append(message)
        }
        
        let priceResult = validateFuelPrice(input.fuelPrice)
        if case .invalid(let message) = priceResult {
            errors.append(message)
        }

        let electricityResult = validateElectricityPricePerKWh(input.electricityPricePerKWh)
        if case .invalid(let message) = electricityResult {
            errors.append(message)
        }
        
        let yearsResult = validateOwnershipYears(input.ownershipYears)
        if case .invalid(let message) = yearsResult {
            errors.append(message)
        }

        let sourceVehicleResult = validateSourceVehicle(input.sourceVehicleId)
        if case .invalid(let message) = sourceVehicleResult {
            errors.append(message)
        }

        let targetVehicleResult = validateTargetVehicle(input.targetVehicleId)
        if case .invalid(let message) = targetVehicleResult {
            errors.append(message)
        }

        let sourcePrice = validatePurchasePrice(input.sourcePurchasePrice, label: L10n.sourcePurchasePriceLabel)
        if case .invalid(let message) = sourcePrice {
            errors.append(message)
        }
        let targetPrice = validatePurchasePrice(input.targetPurchasePrice, label: L10n.targetPurchasePriceLabel)
        if case .invalid(let message) = targetPrice {
            errors.append(message)
        }

        if let ice = input.sourceConsumptionOverrideLPer100Km, (ice < 2 || ice > 25) {
            errors.append(L10n.validationStickerFuelRange)
        }
        if let ev = input.targetEnergyOverrideKWhPer100Km, (ev < 8 || ev > 40) {
            errors.append(L10n.validationStickerEnergyRange)
        }

        let catalog = VehicleCatalogService.shared
        if !input.sourceVehicleId.isEmpty {
            if let source = catalog.vehicle(by: input.sourceVehicleId) {
                let iceOverride = input.sourceConsumptionOverrideLPer100Km.map { $0 / 100.0 }
                if source.powertrain == .ice || source.powertrain == .phev {
                    let liters = iceOverride ?? source.fuelConsumptionLPerKm
                    if (liters ?? 0) <= 0 {
                        errors.append(L10n.validationMissingFuelConsumption)
                    }
                }
                if source.powertrain == .phev {
                    if (source.resolvedEnergyKWhPerKm ?? 0) <= 0 {
                        errors.append(L10n.validationMissingEnergyConsumption)
                    }
                }
            } else {
                errors.append(L10n.validationUnknownSourceVehicle)
            }
        }
        if !input.targetVehicleId.isEmpty {
            if let target = catalog.vehicle(by: input.targetVehicleId) {
                let evOverride = input.targetEnergyOverrideKWhPer100Km.map { $0 / 100.0 }
                if target.powertrain == .ev || target.powertrain == .phev {
                    let kWh = evOverride ?? target.resolvedEnergyKWhPerKm
                    if (kWh ?? 0) <= 0 {
                        errors.append(L10n.validationMissingEnergyConsumption)
                    }
                }
                if target.powertrain == .phev {
                    if (target.fuelConsumptionLPerKm ?? 0) <= 0 {
                        errors.append(L10n.validationMissingFuelConsumption)
                    }
                }
            } else {
                errors.append(L10n.validationUnknownTargetVehicle)
            }
        }
        
        return errors
    }
}

/// Validation result type
enum ValidationResult {
    case valid
    case invalid(String)
}

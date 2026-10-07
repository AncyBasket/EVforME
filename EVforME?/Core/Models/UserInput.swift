//
//  UserInput.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

/// Represents the type of area where the user primarily drives
enum AreaType: String, CaseIterable, Identifiable {
    case urban
    case mixed

    var id: String { rawValue }

    var title: String {
        switch self {
        case .urban: return L10n.areaTypeUrban
        case .mixed: return L10n.areaTypeMixed
        }
    }

    var description: String {
        switch self {
        case .urban: return L10n.areaTypeUrbanDescription
        case .mixed: return L10n.areaTypeMixedDescription
        }
    }

    var iceConsumptionMultiplier: Double {
        switch self {
        case .urban: return 1.08
        case .mixed: return 1.00
        }
    }

    var evConsumptionMultiplier: Double {
        switch self {
        case .urban: return 0.94
        case .mixed: return 1.00
        }
    }

    var kmPerChargeFactor: Double {
        switch self {
        case .urban: return 1.05
        case .mixed: return 0.95
        }
    }
}

/// Profilo di guida tipico (oltre al selettore urbano/misto).
enum TripProfile: String, CaseIterable, Identifiable {
    case custom
    case commuter
    case weekendHighway

    var id: String { rawValue }

    var title: String {
        switch self {
        case .custom: return L10n.tripProfileCustom
        case .commuter: return L10n.tripProfileCommuter
        case .weekendHighway: return L10n.tripProfileWeekend
        }
    }

    var subtitle: String {
        switch self {
        case .custom: return L10n.tripProfileCustomSubtitle
        case .commuter: return L10n.tripProfileCommuterSubtitle
        case .weekendHighway: return L10n.tripProfileWeekendSubtitle
        }
    }

    /// Area suggerita quando si applica il profilo.
    var suggestedAreaType: AreaType {
        switch self {
        case .custom: return .mixed
        case .commuter: return .urban
        case .weekendHighway: return .mixed
        }
    }

    /// Km/anno suggeriti (quick start).
    var suggestedYearlyKm: Int {
        switch self {
        case .custom: return 12_000
        case .commuter: return 18_000
        case .weekendHighway: return 14_000
        }
    }

    /// Extra severità ricarica (autostrada → più energie / cariche).
    var chargeSeverityFactor: Double {
        switch self {
        case .custom: return 1.0
        case .commuter: return 1.02
        case .weekendHighway: return 0.88
        }
    }

    var iceExtraMultiplier: Double {
        switch self {
        case .custom: return 1.0
        case .commuter: return 1.03
        case .weekendHighway: return 1.06
        }
    }

    var evExtraMultiplier: Double {
        switch self {
        case .custom: return 1.0
        case .commuter: return 0.98
        case .weekendHighway: return 1.08
        }
    }
}

/// Modalità di confronto: acquisto nuovo vs auto già possedute (solo opex).
enum ComparisonIntent: String, CaseIterable, Identifiable {
    /// Include premium di listino netto (EV − attuale − incentivi) nel sì/no e nel break-even.
    case consideringPurchase
    /// Solo costi di gestione: premium = 0 (sunk cost). Assicurazione/manutenzione su valore d’uso.
    case alreadyOwned

    var id: String { rawValue }

    var title: String {
        switch self {
        case .consideringPurchase: return L10n.comparisonIntentPurchaseTitle
        case .alreadyOwned: return L10n.comparisonIntentOwnedTitle
        }
    }

    var subtitle: String {
        switch self {
        case .consideringPurchase: return L10n.comparisonIntentPurchaseSubtitle
        case .alreadyOwned: return L10n.comparisonIntentOwnedSubtitle
        }
    }

    /// Default: se entrambe le auto sono di anni già passati → già possedute.
    static func suggested(sourceYear: Int, targetYear: Int, referenceYear: Int = Calendar.current.component(.year, from: Date())) -> ComparisonIntent {
        if sourceYear < referenceYear, targetYear < referenceYear {
            return .alreadyOwned
        }
        return .consideringPurchase
    }
}

/// User input data for EV simulation
struct UserInput {
    /// Kilometers per year (field name is historical).
    var dailyKm: Int
    var hasHomeCharging: Bool
    var areaType: AreaType
    var fuelPrice: Double
    var ownershipYears: Int
    var electricityPricePerKWh: Double
    var sourceVehicleId: String
    var targetVehicleId: String
    var scenario: Scenario

    /// Prezzo di acquisto stimato veicolo attuale (ICE), €.
    var sourcePurchasePrice: Double
    /// Prezzo di acquisto stimato EV target, €.
    var targetPurchasePrice: Double
    /// Include stima incentivi IT (bonus acquisto + esenzione bollo già nei seed EV).
    var includeIncentives: Bool
    /// Compra nuovo vs già possedute (opex only).
    var comparisonIntent: ComparisonIntent
    /// Profilo tragitti tipici.
    var tripProfile: TripProfile
    /// Override consumi ICE da OCR sticker (L/100 km). `nil` = usa catalogo.
    var sourceConsumptionOverrideLPer100Km: Double?
    /// Override energia EV da OCR (kWh/100 km). `nil` = usa catalogo.
    var targetEnergyOverrideKWhPer100Km: Double?
    /// Configurazione ricarica personalizzata
    var chargingConfiguration: ChargingConfiguration

    init(
        dailyKm: Int,
        hasHomeCharging: Bool,
        areaType: AreaType,
        fuelPrice: Double,
        ownershipYears: Int,
        electricityPricePerKWh: Double = 0.25,
        sourceVehicleId: String = "",
        targetVehicleId: String = "",
        scenario: Scenario = .realistic,
        sourcePurchasePrice: Double = 12_000,
        targetPurchasePrice: Double = 32_000,
        includeIncentives: Bool = true,
        comparisonIntent: ComparisonIntent = .consideringPurchase,
        tripProfile: TripProfile = .custom,
        sourceConsumptionOverrideLPer100Km: Double? = nil,
        targetEnergyOverrideKWhPer100Km: Double? = nil,
        chargingConfiguration: ChargingConfiguration = ChargingConfiguration()
    ) {
        self.dailyKm = dailyKm
        self.hasHomeCharging = hasHomeCharging
        self.areaType = areaType
        self.fuelPrice = fuelPrice
        self.ownershipYears = ownershipYears
        self.electricityPricePerKWh = electricityPricePerKWh
        self.sourceVehicleId = sourceVehicleId
        self.targetVehicleId = targetVehicleId
        self.scenario = scenario
        self.sourcePurchasePrice = sourcePurchasePrice
        self.targetPurchasePrice = targetPurchasePrice
        self.includeIncentives = includeIncentives
        self.comparisonIntent = comparisonIntent
        self.tripProfile = tripProfile
        self.sourceConsumptionOverrideLPer100Km = sourceConsumptionOverrideLPer100Km
        self.targetEnergyOverrideKWhPer100Km = targetEnergyOverrideKWhPer100Km
        self.chargingConfiguration = chargingConfiguration
    }

    /// Bonus acquisto stimato (IT, ordine di grandezza — non legale). Solo in modalità acquisto.
    var estimatedPurchaseIncentiveEUR: Double {
        guard comparisonIntent == .consideringPurchase, includeIncentives else { return 0 }
        return ItalianIncentives.estimatedPurchaseBonusEUR(
            evListPrice: targetPurchasePrice,
            replacingVehiclePrice: sourcePurchasePrice,
            hasHomeCharging: hasHomeCharging
        )
    }

    /// Delta di listino netto (EV − ICE − incentivi). Zero se già possedute (sunk cost).
    var netPurchasePremiumEUR: Double {
        guard comparisonIntent == .consideringPurchase else { return 0 }
        return max(0, targetPurchasePrice - sourcePurchasePrice - estimatedPurchaseIncentiveEUR)
    }

    /// Config ricarica allineata ai controlli UI (casa + €/kWh slider).
    /// Usata al momento del calcolo così il verdetto non dipende da stato stale.
    func resolvedChargingConfiguration() -> ChargingConfiguration {
        var config = ChargingCostCalculator.suggestedConfiguration(
            yearlyKm: Double(dailyKm),
            hasHomeCharging: hasHomeCharging
        )
        config.customHomePricePerKWh = electricityPricePerKWh
        return config
    }

    mutating func applyTripProfileDefaults() {
        guard tripProfile != .custom else { return }
        areaType = tripProfile.suggestedAreaType
        dailyKm = tripProfile.suggestedYearlyKm
    }
}

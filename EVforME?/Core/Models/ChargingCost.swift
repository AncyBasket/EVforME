//
//  ChargingCost.swift
//  EVforME?
//
//  Calcolo costi ricarica differenziato per tipo di ricarica
//

import Foundation

/// Tipo di ricarica disponibile
enum ChargingType: String, CaseIterable, Identifiable {
    case home = "home"
    case publicSlow = "public_slow"
    case publicFast = "public_fast"
    case publicUltraFast = "public_ultra_fast"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .home: return L10n.chargingTypeHome
        case .publicSlow: return L10n.chargingTypePublicSlow
        case .publicFast: return L10n.chargingTypePublicFast
        case .publicUltraFast: return L10n.chargingTypePublicUltraFast
        }
    }
    
    var description: String {
        switch self {
        case .home: return L10n.chargingTypeHomeDescription
        case .publicSlow: return L10n.chargingTypePublicSlowDescription
        case .publicFast: return L10n.chargingTypePublicFastDescription
        case .publicUltraFast: return L10n.chargingTypePublicUltraFastDescription
        }
    }
    
    /// Potenza tipica in kW
    var typicalPowerKW: Double {
        switch self {
        case .home: return 7.4 // Wallbox tipico
        case .publicSlow: return 22.0 // AC pubblico
        case .publicFast: return 50.0 // DC fast
        case .publicUltraFast: return 150.0 // Ultra fast
        }
    }
    
    /// Costo base per kWh (€) - Italia 2024
    var baseCostPerKWh: Double {
        switch self {
        case .home: return 0.25 // Prezzo domestico
        case .publicSlow: return 0.45 // AC pubblico
        case .publicFast: return 0.65 // DC fast
        case .publicUltraFast: return 0.85 // Ultra fast
        }
    }
    
    /// Efficienza perdite (0-1, dove 1 = nessuna perdita)
    var efficiency: Double {
        switch self {
        case .home: return 0.92 // AC con perdite
        case .publicSlow: return 0.90 // AC pubblico
        case .publicFast: return 0.85 // DC con conversione
        case .publicUltraFast: return 0.80 // Ultra fast con maggiori perdite
        }
    }
}

/// Configurazione ricarica dell'utente
struct ChargingConfiguration {
    var hasHomeCharging: Bool
    var homeChargingType: ChargingType
    var publicChargingType: ChargingType
    var homeChargingShare: Double // 0-1, quota di ricarica fatta a casa
    var customHomePricePerKWh: Double?
    var customPublicPricePerKWh: Double?
    
    init(
        hasHomeCharging: Bool = true,
        homeChargingType: ChargingType = .home,
        publicChargingType: ChargingType = .publicFast,
        homeChargingShare: Double = 0.8,
        customHomePricePerKWh: Double? = nil,
        customPublicPricePerKWh: Double? = nil
    ) {
        self.hasHomeCharging = hasHomeCharging
        self.homeChargingType = homeChargingType
        self.publicChargingType = publicChargingType
        self.homeChargingShare = hasHomeCharging ? homeChargingShare : 0.0
        self.customHomePricePerKWh = customHomePricePerKWh
        self.customPublicPricePerKWh = customPublicPricePerKWh
    }
    
    /// Costo medio ponderato per kWh in base alla configurazione
    func weightedCostPerKWh() -> Double {
        let homeCost = customHomePricePerKWh ?? homeChargingType.baseCostPerKWh
        let publicCost = customPublicPricePerKWh ?? publicChargingType.baseCostPerKWh
        
        let homeShare = hasHomeCharging ? homeChargingShare : 0.0
        let publicShare = 1.0 - homeShare
        
        return (homeCost * homeShare + publicCost * publicShare)
    }
    
    /// Efficienza media ponderata
    func weightedEfficiency() -> Double {
        let homeShare = hasHomeCharging ? homeChargingShare : 0.0
        let publicShare = 1.0 - homeShare
        
        return (homeChargingType.efficiency * homeShare + publicChargingType.efficiency * publicShare)
    }
}

/// Calcolatore costi ricarica avanzato
struct ChargingCostCalculator {
    
    /// Calcola costo annuale energia per EV con configurazione ricarica personalizzata
    static func calculateAnnualEnergyCost(
        yearlyKm: Double,
        energyConsumptionKWhPerKm: Double,
        chargingConfig: ChargingConfiguration
    ) -> Double {
        let efficiency = chargingConfig.weightedEfficiency()
        let costPerKWh = chargingConfig.weightedCostPerKWh()
        
        // kWh consumati = km × consumo/km
        let totalKWhNeeded = yearlyKm * energyConsumptionKWhPerKm
        
        // kWh effettivi da pagare (tenendo conto dell'efficienza)
        let kWhToPay = totalKWhNeeded / efficiency
        
        return kWhToPay * costPerKWh
    }
    
    /// Calcola costo per 100 km con configurazione specifica
    static func calculateCostPer100Km(
        energyConsumptionKWhPerKm: Double,
        chargingConfig: ChargingConfiguration
    ) -> Double {
        let efficiency = chargingConfig.weightedEfficiency()
        let costPerKWh = chargingConfig.weightedCostPerKWh()
        
        // kWh per 100 km
        let kWhPer100Km = energyConsumptionKWhPerKm * 100
        
        // kWh effettivi da pagare
        let kWhToPay = kWhPer100Km / efficiency
        
        return kWhToPay * costPerKWh
    }
    
    /// Stima tempo di ricarica per un veicolo specifico
    static func estimateChargingTime(
        batteryKWh: Double,
        currentChargePercent: Double,
        targetChargePercent: Double,
        chargingType: ChargingType
    ) -> TimeInterval {
        let chargeNeeded = batteryKWh * (targetChargePercent - currentChargePercent) / 100.0
        let hoursNeeded = chargeNeeded / chargingType.typicalPowerKW
        return hoursNeeded * 3600 // Converti in secondi
    }
    
    /// Genera configurazione suggerita basata sull'uso dell'utente
    static func suggestedConfiguration(
        yearlyKm: Double,
        hasHomeCharging: Bool
    ) -> ChargingConfiguration {
        if hasHomeCharging {
            // Più km fai, più usi ricarica pubblica
            let homeShare: Double
            switch yearlyKm {
            case 0..<10_000:
                homeShare = 0.95
            case 10_000..<20_000:
                homeShare = 0.85
            case 20_000..<30_000:
                homeShare = 0.75
            default:
                homeShare = 0.65
            }
            
            return ChargingConfiguration(
                hasHomeCharging: true,
                homeChargingType: .home,
                publicChargingType: .publicFast,
                homeChargingShare: homeShare
            )
        } else {
            // Solo ricarica pubblica - suggerisci fast charging per uso frequente
            let publicType: ChargingType
            switch yearlyKm {
            case 0..<15_000:
                publicType = .publicSlow
            case 15_000..<25_000:
                publicType = .publicFast
            default:
                publicType = .publicUltraFast
            }
            
            return ChargingConfiguration(
                hasHomeCharging: false,
                homeChargingType: .home,
                publicChargingType: publicType,
                homeChargingShare: 0.0
            )
        }
    }
}
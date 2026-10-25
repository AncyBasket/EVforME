//
//  WeeklyChargeEstimator.swift
//  EVforME?
//
//  Stima ricariche/settimana dall'autonomia dichiarata (WLTP o batteria÷consumo).
//  km per ricarica = autonomia esatta; quota PHEV = stessa del costo energia.
//

import Foundation

enum WeeklyChargeEstimator {
    /// Autonomia usabile per la stima: `wltpRangeKm`, altrimenti batteria ÷ consumo.
    static func declaredRangeKm(for vehicle: VehicleCatalogItem) -> Int? {
        if let range = vehicle.wltpRangeKm, range > 0 {
            return range
        }
        guard let battery = vehicle.batteryKWh, battery > 0,
              let kwhPerKm = vehicle.resolvedEnergyKWhPerKm, kwhPerKm > 0 else {
            return nil
        }
        let derived = Int((battery / kwhPerKm).rounded())
        return derived > 0 ? derived : nil
    }

    /// `nil` = EV/PHEV senza autonomia in catalogo (non inventare 300 km).
    /// `0` = termica/HEV, oppure km settimanali a zero.
    /// - Parameter electricKmShare: quota km elettrici (1 per EV; `phevElectricKmShare` per PHEV).
    static func weeklyCharges(
        yearlyKm: Double,
        powertrain: Powertrain,
        rangeKm: Int?,
        electricKmShare: Double
    ) -> Int? {
        switch powertrain {
        case .ice, .hev:
            return 0
        case .ev, .phev:
            guard let rangeKm, rangeKm > 0 else { return nil }
            let weeklyKm = yearlyKm / 52.0
            if weeklyKm <= 0 { return 0 }
            let kmPerCharge = Double(rangeKm)
            guard kmPerCharge > 0 else { return nil }
            let share = min(1, max(0, electricKmShare))
            let electricWeeklyKm = weeklyKm * share
            if electricWeeklyKm <= 0 { return 0 }
            return max(1, Int(ceil(electricWeeklyKm / kmPerCharge)))
        }
    }
}

/// Copy paura/realtà sulle ricariche: coerente col numero mostrato.
enum ChargingFearCopy {
    /// `nil` = non mostrare la coppia fear/reality (n/d o zero).
    static func reality(for weeklyCharges: Int?) -> String? {
        guard let weeklyCharges, weeklyCharges >= 1 else { return nil }
        if weeklyCharges <= 2 {
            return L10n.realityChargingFewTimes
        }
        return L10n.realityChargingAboutTimes(weeklyCharges)
    }
}

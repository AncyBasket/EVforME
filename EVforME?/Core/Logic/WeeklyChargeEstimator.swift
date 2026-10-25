//
//  WeeklyChargeEstimator.swift
//  EVforME?
//
//  Stima ricariche/settimana dall'autonomia dichiarata (WLTP o batteria÷consumo).
//  Niente baseline fissa da 300 km.
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
    static func weeklyCharges(
        yearlyKm: Double,
        powertrain: Powertrain,
        rangeKm: Int?,
        areaType: AreaType,
        tripProfile: TripProfile
    ) -> Int? {
        switch powertrain {
        case .ice, .hev:
            return 0
        case .ev, .phev:
            guard let rangeKm, rangeKm > 0 else { return nil }
            let weeklyKm = yearlyKm / 52.0
            if weeklyKm <= 0 { return 0 }
            let kmPerCharge = Double(rangeKm)
                * areaType.kmPerChargeFactor
                * tripProfile.chargeSeverityFactor
            guard kmPerCharge > 0 else { return nil }
            let electricWeeklyKm = powertrain == .phev ? weeklyKm * 0.55 : weeklyKm
            return max(1, Int(ceil(electricWeeklyKm / kmPerCharge)))
        }
    }
}

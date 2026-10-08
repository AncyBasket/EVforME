//
//  AppMarket.swift
//  EVforME?
//
//  Paese utente → profilo costi di manutenzione (fonti per cluster).
//

import Foundation

/// Mercato ISO 3166-1 alpha-2 supportato esplicitamente in UI.
enum AppMarket: String, CaseIterable, Identifiable, Codable, Hashable {
    case IT, DE, FR, ES, PT, AT, NL, BE, CH, PL, SE, NO, IE, GB, US, CA, other

    var id: String { rawValue }

    /// Cluster di tariffe (paesi senza studio dedicato ereditano il cluster più vicino).
    enum CostCluster: String {
        /// Quattroruote 2022 + SicurAUTO 2023 (tagliandi IT) + buffer consumabili.
        case southernEU
        /// Tec Alliance / Fuhrpark 2023 + ADAC (DE/EU flotte).
        case centralEU
        /// The Car Expert / Clear Vehicle Data 2024 (UK scheduled servicing).
        case uk
        /// DOE/ANL Burnham 2021 + AAA 2024 (US ¢/mi → € @ 15k km).
        case northAmerica
        /// Media ponderata EU quando il paese non ha fonte dedicata.
        case worldDefault
    }

    var costCluster: CostCluster {
        switch self {
        case .IT, .ES, .PT:
            return .southernEU
        case .DE, .AT, .NL, .BE, .FR, .CH, .PL, .SE, .NO:
            return .centralEU
        case .GB, .IE:
            return .uk
        case .US, .CA:
            return .northAmerica
        case .other:
            return .worldDefault
        }
    }

    /// Etichetta UI (EN/IT con Locale corrente).
    var localizedName: String {
        let locale = Locale.current
        if self == .other {
            return L10n.marketOtherCountry
        }
        return locale.localizedString(forRegionCode: rawValue) ?? rawValue
    }

    static func from(isoCountryCode: String?) -> AppMarket {
        guard let raw = isoCountryCode?.uppercased(), !raw.isEmpty else {
            return .fromDeviceLocale()
        }
        if let exact = AppMarket(rawValue: raw) { return exact }
        // Alias comuni non in enum.
        switch raw {
        case "UK": return .GB
        default: return .other
        }
    }

    static func fromDeviceLocale() -> AppMarket {
        let code = Locale.current.region?.identifier
        return from(isoCountryCode: code)
    }

    /// Paesi mostrati nel picker (ordinati per nome localizzato).
    static var pickerCases: [AppMarket] {
        allCases.sorted { $0.localizedName.localizedCaseInsensitiveCompare($1.localizedName) == .orderedAscending }
    }
}

/// Tariffe manutenzione ordinaria (€/anno) a **15.000 km** e età media (≈4–7 anni).
/// Scalate linearmente sui km; moltiplicatore età da Consumer Reports 2020.
struct MarketMaintenanceRates: Equatable {
    /// €/anno ICE a 15.000 km, età media.
    let iceEURPerYearAt15k: Double
    /// €/anno BEV a 15.000 km, età media.
    let evEURPerYearAt15k: Double
    /// €/anno PHEV a 15.000 km, età media.
    let phevEURPerYearAt15k: Double
    /// Citazione breve per UI/debug.
    let sourceNote: String

    static func rates(for market: AppMarket) -> MarketMaintenanceRates {
        switch market.costCluster {
        case .southernEU:
            // Quattroruote 2022 (6y/90k: EV ~66–96 €/anno tagliandi) + SicurAUTO 2023
            // (8y: ~100–250 €/anno). Buffer consumabili (filtri/fluidi/leggera usura)
            // senza gonfiare al livello DOE USA.
            return MarketMaintenanceRates(
                iceEURPerYearAt15k: 450,
                evEURPerYearAt15k: 140,
                phevEURPerYearAt15k: 320,
                sourceNote: "IT/ES: Quattroruote 2022 + SicurAUTO 2023"
            )
        case .centralEU:
            // Tec Alliance / bfp Fuhrpark 2023: 3y/60k km — EV ~270–380 €/anno,
            // ICE ~460–730 €/anno (es. ID.3 801 vs Golf 1634). Escalato a 15k km.
            return MarketMaintenanceRates(
                iceEURPerYearAt15k: 520,
                evEURPerYearAt15k: 250,
                phevEURPerYearAt15k: 400,
                sourceNote: "DE/EU: Tec Alliance Fuhrpark 2023 (+ ADAC)"
            )
        case .uk:
            // The Car Expert / Clear Vehicle Data 2024: anni 1–3 media
            // EV £518, ICE £733 → € (~1.17). Solo scheduled (no gomme).
            return MarketMaintenanceRates(
                iceEURPerYearAt15k: 860,
                evEURPerYearAt15k: 605,
                phevEURPerYearAt15k: 750,
                sourceNote: "UK: The Car Expert / Clear Vehicle Data 2024"
            )
        case .northAmerica:
            // DOE/ANL 2021: 6.1¢/mi BEV, 10.1¢/mi ICE → €/km @ EURUSD 0.92,
            // annualizzato a 15.000 km (non 15k mi).
            return MarketMaintenanceRates(
                iceEURPerYearAt15k: 866,
                evEURPerYearAt15k: 523,
                phevEURPerYearAt15k: 772,
                sourceNote: "US: DOE/ANL Burnham 2021 (AAA cross-check)"
            )
        case .worldDefault:
            // Media tra southernEU e centralEU (nessuna fonte primaria paese).
            return MarketMaintenanceRates(
                iceEURPerYearAt15k: 485,
                evEURPerYearAt15k: 195,
                phevEURPerYearAt15k: 360,
                sourceNote: "Default: media EU (IT + DE clusters)"
            )
        }
    }
}

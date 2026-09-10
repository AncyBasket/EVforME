//
//  Defaults.swift
//  EVforME?
//

import Foundation

enum Defaults {
    /// App Group condiviso app ↔ widget.
    static let appGroupID = "group.Gancione.EVforME"

    /// Coppia di partenza (con foto) per non lasciare i picker vuoti.
    static let starterSourceVehicleId = "volkswagen-golf-2026"
    static let starterTargetVehicleId = "tesla-model-3-2026"

    /// Stima listino grezza quando l’utente cambia veicolo.
    static func suggestedPurchasePrice(for vehicle: VehicleCatalogItem) -> Double {
        let age = max(0, 2026 - vehicle.year)
        switch vehicle.powertrain {
        case .ice:
            return Double(max(3_500, 16_500 - age * 900))
        case .phev:
            return Double(max(10_000, 28_000 - age * 1_100))
        case .ev:
            return Double(max(14_000, 38_000 - age * 1_300))
        }
    }

    /// Fonti pubbliche prezzi (usate direttamente dall’app a ogni apertura).
    static let mimitFuelPricesCSVURL = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
    static let eurostatElectricityURL =
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_204?geo=IT"

    /// Catalogo veicoli HTTPS pubblico (best-effort).
    /// L’app è **offline-first** sul seed bundlato `vehicles.seed.quality`.
    /// Preferenza URL: `Data/catalog_cdn.json` (aggiornato da `publish_catalog_cdn.py`).
    /// Per TestFlight: lasciare vuoto finché non c’è un host stabile (niente catbox in produzione).
    static let publicVehicleCatalogCDNURL = ""

    private static func bundledCatalogCDNURL() -> String? {
        guard let url = Bundle.main.url(forResource: "catalog_cdn", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let remote = obj["url"] as? String,
              !remote.isEmpty else {
            return nil
        }
        return remote
    }

    private static func plistOrEnv(_ key: String) -> String {
        if let env = ProcessInfo.processInfo.environment[key], !env.isEmpty {
            return env
        }
        if let plist = Bundle.main.object(forInfoDictionaryKey: key) as? String, !plist.isEmpty {
            return plist
        }
        return ""
    }

    /// Catalogo remoto a ogni open (opzionale).
    /// Ordine: env/plist → `catalog_cdn.json` → fallback costante.
    /// Fallimenti → nessun errore utente; si usa il seed bundlato.
    static var vehicleCatalogRemoteURL: String {
        let configured = plistOrEnv("EVFORME_CATALOG_URL")
        if !configured.isEmpty { return configured }
        if let bundled = bundledCatalogCDNURL() { return bundled }
        return publicVehicleCatalogCDNURL
    }

    /// Override opzionale costi via API interna (altrimenti MIMIT + Eurostat).
    static var officialEnergyCostsRemoteURL: String {
        plistOrEnv("EVFORME_ENERGY_URL")
    }

    /// Analytics ingest (POST). Vuoto = solo log locale.
    static var analyticsIngestURL: String {
        let configured = plistOrEnv("EVFORME_ANALYTICS_URL")
        if !configured.isEmpty { return configured }
        #if DEBUG
        return "http://127.0.0.1:8787/events"
        #else
        return ""
        #endif
    }

    /// Lead webhook (POST). Vuoto = solo salvataggio locale.
    static var leadWebhookURL: String {
        let configured = plistOrEnv("EVFORME_LEAD_WEBHOOK_URL")
        if !configured.isEmpty { return configured }
        #if DEBUG
        return "http://127.0.0.1:8787/leads"
        #else
        return ""
        #endif
    }

    /// Privacy Policy pubblica (App Store Connect). Vuoto = solo testo in-app.
    static var privacyPolicyURL: URL? {
        let raw = plistOrEnv("EVFORME_PRIVACY_URL")
        guard !raw.isEmpty, let url = URL(string: raw), url.scheme == "https" else {
            return nil
        }
        return url
    }
}

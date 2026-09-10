//
//  StorageService.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

/// Persists user input and last simulation result
final class StorageService {
    static let shared = StorageService()
    
    private let defaults = UserDefaults.standard
    
    private enum Keys {
        static let lastUserInput = "evforme.lastUserInput"
        static let lastSimulationDate = "evforme.lastSimulationDate"
        static let hasSeenOnboarding = "evforme.hasSeenOnboarding"
        static let lastAutoFuelPrice = "evforme.autocosts.lastFuelPrice"
        static let lastAutoElectricityPrice = "evforme.autocosts.lastElectricityPrice"
        static let userCustomizedFuelPrice = "evforme.autocosts.userCustomizedFuelPrice"
        static let userCustomizedElectricityPrice = "evforme.autocosts.userCustomizedElectricityPrice"
    }
    
    private init() {}
    
    // MARK: - User Input
    
    func saveUserInput(_ input: UserInput) {
        updateCustomizationFlags(for: input)
        do {
            let data = try JSONEncoder().encode(CodableUserInput(from: input))
            defaults.set(data, forKey: Keys.lastUserInput)
        } catch {
            ErrorHandler.shared.handle(
                error,
                context: .storage,
                userMessage: L10n.errorStorageWriteFailed
            )
        }
    }
    
    func loadLastUserInput() -> UserInput? {
        guard let data = defaults.data(forKey: Keys.lastUserInput) else {
            ErrorHandler.shared.handleAppError(
                .dataNotFound,
                context: .storage
            )
            return nil
        }
        
        do {
            let codable = try JSONDecoder().decode(CodableUserInput.self, from: data)
            return codable.toUserInput()
        } catch {
            ErrorHandler.shared.handle(
                error,
                context: .storage,
                userMessage: L10n.errorStorageReadFailed
            )
            return nil
        }
    }
    
    // MARK: - Onboarding
    
    var hasSeenOnboarding: Bool {
        get { defaults.bool(forKey: Keys.hasSeenOnboarding) }
        set { defaults.set(newValue, forKey: Keys.hasSeenOnboarding) }
    }
    
    func markOnboardingSeen() {
        hasSeenOnboarding = true
    }

    /// Applica i costi ufficiali solo se l'utente non ha fatto override manuale.
    /// Strategia: aggiorna il campo se coincide con l'ultimo valore auto-applicato
    /// (oppure se non c'era uno storico).
    @discardableResult
    func applyOfficialCostsIfNeeded(_ costs: OfficialEnergyCosts, to input: inout UserInput) -> Bool {
        let epsilon = 0.0001
        let prevAutoFuel = defaults.object(forKey: Keys.lastAutoFuelPrice) as? Double
        let prevAutoElec = defaults.object(forKey: Keys.lastAutoElectricityPrice) as? Double
        let hasStoredInput = defaults.data(forKey: Keys.lastUserInput) != nil
        let userCustomizedFuel = defaults.bool(forKey: Keys.userCustomizedFuelPrice)
        let userCustomizedElec = defaults.bool(forKey: Keys.userCustomizedElectricityPrice)

        var changed = false
        let fuelMatchesPreviousAuto = prevAutoFuel.map { abs(input.fuelPrice - $0) < epsilon } ?? false
        let canAutoApplyFuel = !userCustomizedFuel && (
            prevAutoFuel == nil ? !hasStoredInput : fuelMatchesPreviousAuto
        )
        if canAutoApplyFuel {
            if abs(input.fuelPrice - costs.fuelPricePerLiter) >= epsilon {
                input.fuelPrice = costs.fuelPricePerLiter
                changed = true
            }
        }
        let elecMatchesPreviousAuto = prevAutoElec.map { abs(input.electricityPricePerKWh - $0) < epsilon } ?? false
        let canAutoApplyElec = !userCustomizedElec && (
            prevAutoElec == nil ? !hasStoredInput : elecMatchesPreviousAuto
        )
        if canAutoApplyElec {
            if abs(input.electricityPricePerKWh - costs.electricityPricePerKWh) >= epsilon {
                input.electricityPricePerKWh = costs.electricityPricePerKWh
                changed = true
            }
        }

        defaults.set(costs.fuelPricePerLiter, forKey: Keys.lastAutoFuelPrice)
        defaults.set(costs.electricityPricePerKWh, forKey: Keys.lastAutoElectricityPrice)
        if canAutoApplyFuel {
            defaults.set(false, forKey: Keys.userCustomizedFuelPrice)
        }
        if canAutoApplyElec {
            defaults.set(false, forKey: Keys.userCustomizedElectricityPrice)
        }
        return changed
    }

    private func updateCustomizationFlags(for input: UserInput) {
        let epsilon = 0.0001
        let prevAutoFuel = defaults.object(forKey: Keys.lastAutoFuelPrice) as? Double
        let prevAutoElec = defaults.object(forKey: Keys.lastAutoElectricityPrice) as? Double

        if let prevAutoFuel {
            let customizedFuel = abs(input.fuelPrice - prevAutoFuel) >= epsilon
            defaults.set(customizedFuel, forKey: Keys.userCustomizedFuelPrice)
        }
        if let prevAutoElec {
            let customizedElec = abs(input.electricityPricePerKWh - prevAutoElec) >= epsilon
            defaults.set(customizedElec, forKey: Keys.userCustomizedElectricityPrice)
        }
    }

    /// Marca il prezzo carburante come override utente (es. bump dal widget).
    func markFuelPriceCustomized() {
        defaults.set(true, forKey: Keys.userCustomizedFuelPrice)
        let suite = UserDefaults(suiteName: Defaults.appGroupID) ?? defaults
        suite.set(true, forKey: Keys.userCustomizedFuelPrice)
    }

    /// Importa flag “fuel customized” scritto dal widget via App Group.
    func importWidgetFuelCustomizationFlag() {
        let suite = UserDefaults(suiteName: Defaults.appGroupID) ?? defaults
        if suite.bool(forKey: Keys.userCustomizedFuelPrice) {
            defaults.set(true, forKey: Keys.userCustomizedFuelPrice)
        }
    }
}

// MARK: - Growth instrumentation

enum GrowthEvent: String {
    case onboardingCompleted = "onboarding_completed"
    case simulationStarted = "simulation_started"
    case verdictShown = "verdict_shown"
    case reportRequested = "report_requested"
    case leadSubmitted = "lead_submitted"
}

struct GrowthLogEntry: Codable {
    let event: String
    let timestamp: TimeInterval
    let params: [String: String]
}

final class GrowthTracker {
    static let shared = GrowthTracker()
    private let defaults = UserDefaults.standard
    private let eventsKey = "evforme.growth.events.log"
    private let maxStoredEvents = 500

    private init() {}

    func track(_ event: GrowthEvent, _ params: [String: String] = [:]) {
        persist(event: event, params: params)
        let payload = params
            .map { "\($0.key)=\($0.value)" }
            .sorted()
            .joined(separator: ",")
        print("[Growth] \(event.rawValue)\(payload.isEmpty ? "" : " {\(payload)}")")
        Task.detached(priority: .utility) {
            await RemoteGrowthClient.postEvent(name: event.rawValue, params: params)
        }
    }

    func funnelSnapshot() -> [String: Int] {
        var counts: [String: Int] = [:]
        for entry in loadEntries() {
            counts[entry.event, default: 0] += 1
        }
        return counts
    }

    func exportEventsJSON() -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(loadEntries()),
              let json = String(data: data, encoding: .utf8) else {
            return "[]"
        }
        return json
    }

    func clearEvents() {
        defaults.removeObject(forKey: eventsKey)
    }

    private func persist(event: GrowthEvent, params: [String: String]) {
        var entries = loadEntries()
        entries.append(GrowthLogEntry(
            event: event.rawValue,
            timestamp: Date().timeIntervalSince1970,
            params: params
        ))
        if entries.count > maxStoredEvents {
            entries.removeFirst(entries.count - maxStoredEvents)
        }
        if let data = try? JSONEncoder().encode(entries) {
            defaults.set(data, forKey: eventsKey)
        }
    }

    private func loadEntries() -> [GrowthLogEntry] {
        guard let data = defaults.data(forKey: eventsKey),
              let entries = try? JSONDecoder().decode([GrowthLogEntry].self, from: data) else {
            return []
        }
        return entries
    }
}

/// Invio remoto opzionale (URL da Info.plist / env). Se vuoto, no-op.
enum RemoteGrowthClient {
    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 12
        return URLSession(configuration: config)
    }()

    static func postEvent(name: String, params: [String: String]) async {
        guard let url = URL(string: Defaults.analyticsIngestURL), !Defaults.analyticsIngestURL.isEmpty else {
            return
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "event": name,
            "timestamp": Date().timeIntervalSince1970,
            "params": params,
            "app": "EVforME?",
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        _ = try? await session.data(for: request)
    }

    static func postLead(name: String, email: String, city: String, consent: Bool) async -> Bool {
        guard let url = URL(string: Defaults.leadWebhookURL), !Defaults.leadWebhookURL.isEmpty else {
            return false
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "name": name,
            "email": email,
            "city": city,
            "consent": consent,
            "timestamp": Date().timeIntervalSince1970,
            "source": "EVforME?",
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        do {
            let (_, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200...299).contains(http.statusCode)
        } catch {
            return false
        }
    }
}

enum ReportPriceVariant: String {
    case low = "4.99"
    case high = "9.99"

    var amount: String { rawValue }
}

final class PricingExperimentService {
    static let shared = PricingExperimentService()

    private let defaults = UserDefaults.standard
    private let key = "evforme.pricing.report.variant"

    private init() {}

    var reportVariant: ReportPriceVariant {
        if let raw = defaults.string(forKey: key), let existing = ReportPriceVariant(rawValue: raw) {
            return existing
        }
        let assigned: ReportPriceVariant = Bool.random() ? .low : .high
        defaults.set(assigned.rawValue, forKey: key)
        return assigned
    }
}

// Codable wrapper for UserInput (UserInput uses enums that need custom encoding)
private struct CodableUserInput: Codable {
    let dailyKm: Int
    let hasHomeCharging: Bool
    let areaTypeRaw: Int  // 0 = urban, 1 = mixed
    let fuelPrice: Double
    let ownershipYears: Int
    let electricityPricePerKWh: Double
    let sourceVehicleId: String
    let targetVehicleId: String
    let scenarioRaw: Double
    let sourcePurchasePrice: Double
    let targetPurchasePrice: Double
    let includeIncentives: Bool
    let tripProfileRaw: String
    let sourceConsumptionOverrideLPer100Km: Double?
    let targetEnergyOverrideKWhPer100Km: Double?
    private var chargingConfigData: ChargingConfigData?

    private enum CodingKeys: String, CodingKey {
        case dailyKm
        case hasHomeCharging
        case areaTypeRaw
        case fuelPrice
        case ownershipYears
        case electricityPricePerKWh
        case sourceVehicleId
        case targetVehicleId
        case sourceVehicleRaw
        case targetVehicleRaw
        case scenarioRaw
        case sourcePurchasePrice
        case targetPurchasePrice
        case includeIncentives
        case tripProfileRaw
        case sourceConsumptionOverrideLPer100Km
        case targetEnergyOverrideKWhPer100Km
        case chargingConfigData
    }
    
    // Helper struct for encoding charging configuration
    struct ChargingConfigData: Codable {
        let hasHomeCharging: Bool
        let homeChargingTypeRaw: String
        let publicChargingTypeRaw: String
        let homeChargingShare: Double
        let customHomePricePerKWh: Double?
        let customPublicPricePerKWh: Double?
    }
    
    init(from input: UserInput) {
        dailyKm = input.dailyKm
        hasHomeCharging = input.hasHomeCharging
        areaTypeRaw = input.areaType == .urban ? 0 : 1
        fuelPrice = input.fuelPrice
        ownershipYears = input.ownershipYears
        electricityPricePerKWh = input.electricityPricePerKWh
        sourceVehicleId = input.sourceVehicleId
        targetVehicleId = input.targetVehicleId
        scenarioRaw = input.scenario.rawValue
        sourcePurchasePrice = input.sourcePurchasePrice
        targetPurchasePrice = input.targetPurchasePrice
        includeIncentives = input.includeIncentives
        tripProfileRaw = input.tripProfile.rawValue
        sourceConsumptionOverrideLPer100Km = input.sourceConsumptionOverrideLPer100Km
        targetEnergyOverrideKWhPer100Km = input.targetEnergyOverrideKWhPer100Km
        
        // Encode charging configuration
        chargingConfigData = ChargingConfigData(
            hasHomeCharging: input.chargingConfiguration.hasHomeCharging,
            homeChargingTypeRaw: input.chargingConfiguration.homeChargingType.rawValue,
            publicChargingTypeRaw: input.chargingConfiguration.publicChargingType.rawValue,
            homeChargingShare: input.chargingConfiguration.homeChargingShare,
            customHomePricePerKWh: input.chargingConfiguration.customHomePricePerKWh,
            customPublicPricePerKWh: input.chargingConfiguration.customPublicPricePerKWh
        )
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        dailyKm = try container.decode(Int.self, forKey: .dailyKm)
        hasHomeCharging = try container.decode(Bool.self, forKey: .hasHomeCharging)
        areaTypeRaw = try container.decode(Int.self, forKey: .areaTypeRaw)
        fuelPrice = try container.decode(Double.self, forKey: .fuelPrice)
        ownershipYears = try container.decode(Int.self, forKey: .ownershipYears)
        electricityPricePerKWh = try container.decodeIfPresent(Double.self, forKey: .electricityPricePerKWh) ?? 0.25
        sourceVehicleId = try container.decodeIfPresent(String.self, forKey: .sourceVehicleId)
            ?? Self.migrateLegacySourceVehicleId(
                try container.decodeIfPresent(String.self, forKey: .sourceVehicleRaw)
            )
        targetVehicleId = try container.decodeIfPresent(String.self, forKey: .targetVehicleId)
            ?? Self.migrateLegacyTargetVehicleId(
                try container.decodeIfPresent(String.self, forKey: .targetVehicleRaw)
            )
        scenarioRaw = try container.decode(Double.self, forKey: .scenarioRaw)
        sourcePurchasePrice = try container.decodeIfPresent(Double.self, forKey: .sourcePurchasePrice) ?? 12_000
        targetPurchasePrice = try container.decodeIfPresent(Double.self, forKey: .targetPurchasePrice) ?? 32_000
        includeIncentives = try container.decodeIfPresent(Bool.self, forKey: .includeIncentives) ?? true
        tripProfileRaw = try container.decodeIfPresent(String.self, forKey: .tripProfileRaw) ?? TripProfile.custom.rawValue
        sourceConsumptionOverrideLPer100Km = try container.decodeIfPresent(Double.self, forKey: .sourceConsumptionOverrideLPer100Km)
        targetEnergyOverrideKWhPer100Km = try container.decodeIfPresent(Double.self, forKey: .targetEnergyOverrideKWhPer100Km)
        
        // Persist raw charging payload; `toUserInput()` materializes / falls back.
        chargingConfigData = try container.decodeIfPresent(ChargingConfigData.self, forKey: .chargingConfigData)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(dailyKm, forKey: .dailyKm)
        try container.encode(hasHomeCharging, forKey: .hasHomeCharging)
        try container.encode(areaTypeRaw, forKey: .areaTypeRaw)
        try container.encode(fuelPrice, forKey: .fuelPrice)
        try container.encode(ownershipYears, forKey: .ownershipYears)
        try container.encode(electricityPricePerKWh, forKey: .electricityPricePerKWh)
        try container.encode(sourceVehicleId, forKey: .sourceVehicleId)
        try container.encode(targetVehicleId, forKey: .targetVehicleId)
        try container.encode(scenarioRaw, forKey: .scenarioRaw)
        try container.encode(sourcePurchasePrice, forKey: .sourcePurchasePrice)
        try container.encode(targetPurchasePrice, forKey: .targetPurchasePrice)
        try container.encode(includeIncentives, forKey: .includeIncentives)
        try container.encode(tripProfileRaw, forKey: .tripProfileRaw)
        try container.encodeIfPresent(sourceConsumptionOverrideLPer100Km, forKey: .sourceConsumptionOverrideLPer100Km)
        try container.encodeIfPresent(targetEnergyOverrideKWhPer100Km, forKey: .targetEnergyOverrideKWhPer100Km)
        try container.encodeIfPresent(chargingConfigData, forKey: .chargingConfigData)
    }
    
    func toUserInput() -> UserInput {
        let scenario = Scenario.allCases.first { $0.rawValue == scenarioRaw } ?? .realistic
        let trip = TripProfile(rawValue: tripProfileRaw) ?? .custom
        
        // For backward compatibility, use suggested configuration if charging config data is missing
        let chargingConfig: ChargingConfiguration
        if let configData = chargingConfigData {
            chargingConfig = ChargingConfiguration(
                hasHomeCharging: configData.hasHomeCharging,
                homeChargingType: ChargingType(rawValue: configData.homeChargingTypeRaw) ?? .home,
                publicChargingType: ChargingType(rawValue: configData.publicChargingTypeRaw) ?? .publicFast,
                homeChargingShare: configData.homeChargingShare,
                customHomePricePerKWh: configData.customHomePricePerKWh,
                customPublicPricePerKWh: configData.customPublicPricePerKWh
            )
        } else {
            // Fallback for backward compatibility
            chargingConfig = ChargingCostCalculator.suggestedConfiguration(
                yearlyKm: Double(dailyKm),
                hasHomeCharging: hasHomeCharging
            )
        }
        
        return UserInput(
            dailyKm: dailyKm,
            hasHomeCharging: hasHomeCharging,
            areaType: areaTypeRaw == 0 ? .urban : .mixed,
            fuelPrice: fuelPrice,
            ownershipYears: ownershipYears,
            electricityPricePerKWh: electricityPricePerKWh,
            sourceVehicleId: sourceVehicleId,
            targetVehicleId: targetVehicleId,
            scenario: scenario,
            sourcePurchasePrice: sourcePurchasePrice,
            targetPurchasePrice: targetPurchasePrice,
            includeIncentives: includeIncentives,
            tripProfile: trip,
            sourceConsumptionOverrideLPer100Km: sourceConsumptionOverrideLPer100Km,
            targetEnergyOverrideKWhPer100Km: targetEnergyOverrideKWhPer100Km,
            chargingConfiguration: chargingConfig
        )
    }

    private static func migrateLegacySourceVehicleId(_ legacy: String?) -> String {
        switch legacy {
        case "iceCompact": return "fiat-panda-2024"
        case "iceSuv": return "toyota-rav4-2024"
        default: return ""
        }
    }

    private static func migrateLegacyTargetVehicleId(_ legacy: String?) -> String {
        switch legacy {
        case "evCompact": return "renault-zoe-2024"
        case "evSuv": return "hyundai-kona-ev-2024"
        default: return ""
        }
    }
}

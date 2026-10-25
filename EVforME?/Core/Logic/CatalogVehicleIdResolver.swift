//
//  CatalogVehicleIdResolver.swift
//  EVforME?
//
//  Resolves persisted catalog ids after rows are removed or renamed.
//  Missing ids must not crash — fall back to starter defaults.
//

import Foundation

enum CatalogVehicleIdResolver {
    /// Explicit remaps (old id → new id). Extended by later catalog PRs (e.g. Model 3 trims).
    static var aliases: [String: String] = [:]

    /// Resolve a persisted id to a catalog row id that still exists, or `nil` if none.
    static func resolveId(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared
    ) -> String? {
        let trimmed = rawId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        let mapped = aliases[trimmed] ?? trimmed
        if catalog.vehicle(by: mapped) != nil {
            return mapped
        }
        return nil
    }

    /// Source vehicle: alias → catalog hit → starter source → first ICE/HEV source → nil.
    static func resolveSourceId(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared
    ) -> String {
        if let id = resolveId(rawId, catalog: catalog) {
            return id
        }
        if catalog.vehicle(by: Defaults.starterSourceVehicleId) != nil {
            return Defaults.starterSourceVehicleId
        }
        return catalog.sourceVehicles().first?.id ?? Defaults.starterSourceVehicleId
    }

    /// Target EV: alias → catalog hit → starter target → first target EV → empty (picker).
    static func resolveTargetId(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared
    ) -> String {
        if let id = resolveId(rawId, catalog: catalog) {
            return id
        }
        if catalog.vehicle(by: Defaults.starterTargetVehicleId) != nil {
            return Defaults.starterTargetVehicleId
        }
        return catalog.targetEVVehicles().first?.id ?? ""
    }

    /// Mutates input so saved ids always point at live catalog rows (or safe defaults).
    @discardableResult
    static func sanitizeUserInput(
        _ input: inout UserInput,
        catalog: VehicleCatalogService = .shared
    ) -> Bool {
        let beforeSource = input.sourceVehicleId
        let beforeTarget = input.targetVehicleId
        input.sourceVehicleId = resolveSourceId(beforeSource, catalog: catalog)
        input.targetVehicleId = resolveTargetId(beforeTarget, catalog: catalog)
        return beforeSource != input.sourceVehicleId || beforeTarget != input.targetVehicleId
    }
}

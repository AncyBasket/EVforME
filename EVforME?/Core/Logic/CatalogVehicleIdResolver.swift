//
//  CatalogVehicleIdResolver.swift
//  EVforME?
//
//  Resolves persisted catalog ids after rows are removed or renamed.
//  Missing ids must not crash — and must not silently show another car's numbers
//  under a stale label.
//

import Foundation

enum CatalogVehicleIdResolver {
    /// Explicit remaps (old id → new id). Extended by later catalog PRs.
    static let defaultAliases: [String: String] = [:]

    static var aliases: [String: String] = defaultAliases

    static func resetAliasesForTesting() {
        aliases = defaultAliases
    }

    /// Resolve to a live catalog id, or `nil` if the id is gone (and not aliased).
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

    /// True when the raw saved id is no longer in the catalog and has no alias.
    static func isUnavailable(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared
    ) -> Bool {
        let trimmed = rawId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        if catalog.vehicle(by: trimmed) != nil { return false }
        if let mapped = aliases[trimmed], catalog.vehicle(by: mapped) != nil {
            return false
        }
        return true
    }

    /// Both source and target resolve to live catalog rows (aliases OK; no starter fallback).
    static func hasResolvableVehiclePair(
        _ input: UserInput,
        catalog: VehicleCatalogService = .shared
    ) -> Bool {
        resolveId(input.sourceVehicleId, catalog: catalog) != nil
            && resolveId(input.targetVehicleId, catalog: catalog) != nil
    }

    static func resolveSourceId(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared,
        fallbackToStarter: Bool = true
    ) -> String {
        if let id = resolveId(rawId, catalog: catalog) {
            return id
        }
        guard fallbackToStarter else { return "" }
        if catalog.vehicle(by: Defaults.starterSourceVehicleId) != nil {
            return Defaults.starterSourceVehicleId
        }
        return catalog.sourceVehicles().first?.id ?? Defaults.starterSourceVehicleId
    }

    static func resolveTargetId(
        _ rawId: String,
        catalog: VehicleCatalogService = .shared,
        fallbackToStarter: Bool = true
    ) -> String {
        if let id = resolveId(rawId, catalog: catalog) {
            return id
        }
        guard fallbackToStarter else { return "" }
        if catalog.vehicle(by: Defaults.starterTargetVehicleId) != nil {
            return Defaults.starterTargetVehicleId
        }
        return catalog.targetEVVehicles().first?.id ?? ""
    }

    /// - Parameter fallbackToStarter: `false` for history restore (empty id → user must pick).
    @discardableResult
    static func sanitizeUserInput(
        _ input: inout UserInput,
        catalog: VehicleCatalogService = .shared,
        fallbackToStarter: Bool = true
    ) -> Bool {
        let beforeSource = input.sourceVehicleId
        let beforeTarget = input.targetVehicleId
        input.sourceVehicleId = resolveSourceId(
            beforeSource,
            catalog: catalog,
            fallbackToStarter: fallbackToStarter
        )
        input.targetVehicleId = resolveTargetId(
            beforeTarget,
            catalog: catalog,
            fallbackToStarter: fallbackToStarter
        )
        return beforeSource != input.sourceVehicleId || beforeTarget != input.targetVehicleId
    }

    /// Label for history UI: never present a removed id as if it were still valid.
    static func historyLabel(
        rawId: String,
        savedDisplayName: String?,
        catalog: VehicleCatalogService = .shared
    ) -> String {
        if let live = catalog.vehicle(by: rawId) {
            return savedDisplayName ?? live.displayName
        }
        if let mapped = aliases[rawId], let live = catalog.vehicle(by: mapped) {
            return live.displayName
        }
        let fallen = savedDisplayName ?? rawId
        return L10n.catalogVehicleNoLongerAvailable(fallen)
    }
}

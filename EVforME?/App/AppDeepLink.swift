//
//  AppDeepLink.swift
//  EVforME?
//
//  URL scheme + App Group flag for Shortcuts / Widget / reminder → ultimo verdetto.
//

import Foundation

enum AppDeepLink {
    static let urlScheme = "evforme"
    static let verdictHost = "verdict"
    static let recalculateHost = "recalculate"
    static let verdictURL = URL(string: "\(urlScheme)://\(verdictHost)")!
    static let recalculateURL = URL(string: "\(urlScheme)://\(recalculateHost)")!

    private static let pendingOpenKey = "evforme.pendingOpenLastVerdict"
    private static let pendingRecalcKey = "evforme.pendingRecalculateLast"

    private static var suite: UserDefaults {
        UserDefaults(suiteName: Defaults.appGroupID) ?? .standard
    }

    static func matches(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == urlScheme else { return false }
        let host = url.host?.lowercased()
        return host == verdictHost || host == recalculateHost
    }

    static func isRecalculate(_ url: URL) -> Bool {
        url.scheme?.lowercased() == urlScheme && url.host?.lowercased() == recalculateHost
    }

    static func requestOpenLastVerdict() {
        suite.set(true, forKey: pendingOpenKey)
    }

    static func requestRecalculateLastComparison() {
        suite.set(true, forKey: pendingRecalcKey)
    }

    @discardableResult
    static func consumeOpenLastVerdictRequest() -> Bool {
        let pending = suite.bool(forKey: pendingOpenKey)
        if pending {
            suite.set(false, forKey: pendingOpenKey)
        }
        return pending
    }

    @discardableResult
    static func consumeRecalculateLastRequest() -> Bool {
        let pending = suite.bool(forKey: pendingRecalcKey)
        if pending {
            suite.set(false, forKey: pendingRecalcKey)
        }
        return pending
    }
}

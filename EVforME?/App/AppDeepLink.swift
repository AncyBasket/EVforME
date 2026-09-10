//
//  AppDeepLink.swift
//  EVforME?
//
//  URL scheme + App Group flag for Shortcuts / Widget → ultimo verdetto.
//

import Foundation

enum AppDeepLink {
    static let urlScheme = "evforme"
    static let verdictHost = "verdict"
    static let verdictURL = URL(string: "\(urlScheme)://\(verdictHost)")!

    private static let pendingKey = "evforme.pendingOpenLastVerdict"

    private static var suite: UserDefaults {
        UserDefaults(suiteName: Defaults.appGroupID) ?? .standard
    }

    static func matches(_ url: URL) -> Bool {
        url.scheme?.lowercased() == urlScheme && url.host?.lowercased() == verdictHost
    }

    static func requestOpenLastVerdict() {
        suite.set(true, forKey: pendingKey)
    }

    @discardableResult
    static func consumeOpenLastVerdictRequest() -> Bool {
        let pending = suite.bool(forKey: pendingKey)
        if pending {
            suite.set(false, forKey: pendingKey)
        }
        return pending
    }
}

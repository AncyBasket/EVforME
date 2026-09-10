//
//  ReviewPromptService.swift
//  EVforME?
//

import Foundation
import StoreKit
import SwiftUI

enum ReviewPromptService {
    private static let verdictCountKey = "evforme.review.verdictCount"
    private static let lastPromptAtKey = "evforme.review.lastPromptAt"
    private static let minVerdicts = 2
    private static let minDaysBetweenPrompts = 90.0

    static func recordVerdictShown() {
        let defaults = UserDefaults.standard
        defaults.set(defaults.integer(forKey: verdictCountKey) + 1, forKey: verdictCountKey)
    }

    @MainActor
    static func maybeRequestReview(_ requestReview: RequestReviewAction) {
        let defaults = UserDefaults.standard
        let count = defaults.integer(forKey: verdictCountKey)
        guard count >= minVerdicts else { return }

        if let last = defaults.object(forKey: lastPromptAtKey) as? TimeInterval {
            let days = (Date().timeIntervalSince1970 - last) / 86_400
            guard days >= minDaysBetweenPrompts else { return }
        }

        requestReview()
        defaults.set(Date().timeIntervalSince1970, forKey: lastPromptAtKey)
    }
}

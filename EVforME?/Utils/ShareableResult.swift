//
//  ShareableResult.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

extension SimulationResult {
    /// Text summary for sharing (e.g. Messages, Mail)
    var shareableText: String {
        let verdictLine: String
        switch verdict {
        case .yes: verdictLine = L10n.shareVerdictYes
        case .maybe: verdictLine = L10n.shareVerdictMaybe
        case .notYet: verdictLine = L10n.shareVerdictNotYet
        }
        var lines = [
            L10n.shareTitle,
            "",
            verdictLine,
            "",
            L10n.shareWeeklyCharges(weeklyCharges),
            L10n.shareYearlySavings(yearlySavingsRange.lowerBound, yearlySavingsRange.upperBound),
            "",
            L10n.shareKeyReasons,
        ]
        lines.append(contentsOf: keyReasons.map { "• \($0)" })
        lines.append("")
        lines.append(L10n.shareSignature)
        return lines.joined(separator: "\n")
    }
}

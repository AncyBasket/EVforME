//
//  Typography.swift
//  EVforME?
//
//  Serif per brand/verdetto; sans per UI. Scala con Dynamic Type.
//

import SwiftUI

enum Typography {
    static let mastheadWordmark = Font.system(.title2, design: .serif).weight(.bold)

    static let display = Font.system(.largeTitle, design: .serif).weight(.bold)
    static let title = Font.system(.title2, design: .serif).weight(.semibold)
    static let title2 = Font.system(.headline, design: .default).weight(.semibold)
    static let sectionEyebrow = Font.system(.caption, design: .default).weight(.semibold)
    static let subtitle = Font.system(.body, design: .serif)
    static let body = Font.system(.body, design: .default)
    static let bodyBold = Font.system(.body, design: .default).weight(.semibold)
    static let small = Font.system(.subheadline, design: .default)
    static let caption = Font.system(.caption, design: .default).weight(.medium)
    static let metric = Font.system(.title, design: .serif).weight(.semibold)

    static let verdictTitle = Font.system(.largeTitle, design: .serif).weight(.bold)
    /// Metriche di prova sotto il verdetto.
    static let verdictMetricValue = Font.system(.title2, design: .serif).weight(.semibold)
    static let verdictMetricLabel = Font.system(.caption2, design: .default).weight(.semibold)

    static let readingTitle = Font.system(.title, design: .serif).weight(.semibold)
    static let readingIntro = Font.system(.body, design: .serif)
    static let readingBody = Font.system(.body, design: .default)
    static let readingCardTitle = Font.system(.headline, design: .default).weight(.semibold)
    static let readingCaption = Font.system(.footnote, design: .default).weight(.medium)
}

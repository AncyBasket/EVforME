//
//  Typography.swift
//  EVforME?
//
//  Serif per brand/verdetto; sans per UI. Contrasto tipografico forte.
//

import SwiftUI

enum Typography {
    static let mastheadWordmark = Font.system(size: 28, weight: .bold, design: .serif)

    static let display = Font.system(size: 40, weight: .bold, design: .serif)
    static let title = Font.system(size: 26, weight: .semibold, design: .serif)
    static let title2 = Font.system(size: 18, weight: .semibold, design: .default)
    static let sectionEyebrow = Font.system(size: 12, weight: .semibold, design: .default)
    static let subtitle = Font.system(size: 17, weight: .regular, design: .serif)
    static let body = Font.system(size: 16, weight: .regular, design: .default)
    static let bodyBold = Font.system(size: 16, weight: .semibold, design: .default)
    static let small = Font.system(size: 14, weight: .regular, design: .default)
    static let caption = Font.system(size: 12, weight: .medium, design: .default)
    static let metric = Font.system(size: 28, weight: .semibold, design: .serif)

    static let verdictTitle = Font.system(size: 52, weight: .bold, design: .serif)
    /// Metriche di prova sotto il verdetto.
    static let verdictMetricValue = Font.system(size: 22, weight: .semibold, design: .serif)
    static let verdictMetricLabel = Font.system(size: 11, weight: .semibold, design: .default)

    static let readingTitle = Font.system(size: 28, weight: .semibold, design: .serif)
    static let readingIntro = Font.system(size: 17, weight: .regular, design: .serif)
    static let readingBody = Font.system(size: 16, weight: .regular, design: .default)
    static let readingCardTitle = Font.system(size: 16, weight: .semibold, design: .default)
    static let readingCaption = Font.system(size: 13, weight: .medium, design: .default)
}

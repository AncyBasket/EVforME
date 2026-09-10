//
//  WidgetL10n.swift
//  EVforMEWidget
//
//  Stringhe localizzate per widget e Live Activity (bundle dell’extension).
//

import Foundation

enum WidgetL10n {
    static func string(_ key: String) -> String {
        NSLocalizedString(key, tableName: nil, bundle: .main, value: key, comment: "")
    }

    static func format(_ key: String, _ arguments: CVarArg...) -> String {
        String(format: string(key), arguments: arguments)
    }

    static var brandTitle: String { string("widget_brand_title") }
    static var brandShort: String { string("live_activity_brand_short") }
    static var brandFull: String { string("live_activity_brand") }
    static var emptyPrompt: String { string("widget_empty_prompt") }
    static var bumpFuelTitle: String { string("widget_bump_fuel_title") }
    static var fuelBumpedTitle: String { string("widget_fuel_bumped_title") }
    static var placeholderTitle: String { string("widget_placeholder_title") }
    static var placeholderSubtitle: String { string("widget_placeholder_subtitle") }
    static var configDisplayName: String { string("widget_config_display_name") }
    static var configDescription: String { string("widget_config_description") }
    static var kmPerYearLabel: String { string("live_activity_km_per_year_label") }

    static func savingsChargesLine(min: Int, max: Int, charges: Int) -> String {
        format("widget_savings_charges_line", min, max, charges)
    }

    static func fuelKmLine(price: Double, km: Int) -> String {
        format("widget_fuel_km_line", price, km)
    }

    static func fuelPricePerLiter(_ price: Double) -> String {
        format("widget_fuel_price_per_liter", price)
    }

    static func chargesPerWeek(_ n: Int) -> String {
        format("live_activity_charges_per_week", n)
    }

    static func kmPerYear(_ km: Int) -> String {
        format("live_activity_km_per_year", km)
    }

    static func breakEvenMonths(_ months: Int) -> String {
        format("live_activity_break_even_months", months)
    }

    static func fuelPrice(_ price: Double) -> String {
        format("live_activity_fuel_price", price)
    }
}

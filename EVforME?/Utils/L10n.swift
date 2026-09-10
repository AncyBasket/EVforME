//
//  L10n.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//
//  Usa la lingua del dispositivo: NSLocalizedString con Bundle.main
//  rispetta automaticamente le preferenze lingua (Impostazioni > Generali > Lingua e area).
//

import Foundation

enum L10n {
    /// Bundle da cui leggere le stringhe (rispetta la lingua del dispositivo).
    private static let bundle: Bundle = .main

    /// Restituisce la stringa localizzata per la chiave. La lingua è quella del dispositivo.
    static func string(_ key: String) -> String {
        NSLocalizedString(key, tableName: nil, bundle: bundle, value: key, comment: "")
    }

    static func format(_ key: String, _ arguments: CVarArg...) -> String {
        String(format: string(key), arguments: arguments)
    }
    
    // MARK: - App
    static var appTitle: String { string("app_title") }
    
    // MARK: - Input
    static var dailyKmQuestion: String { string("daily_km_question") }
    static var inputHeroSubtitle: String { string("input_hero_subtitle") }
    static var inputHeroBadge: String { string("input_hero_badge") }
    static var inputSection1Title: String { string("input_section_1_title") }
    static var inputSection1Subtitle: String { string("input_section_1_subtitle") }
    static var inputSection2Title: String { string("input_section_2_title") }
    static var inputSection2Subtitle: String { string("input_section_2_subtitle") }
    static var inputSection3Title: String { string("input_section_3_title") }
    static var inputSection3Subtitle: String { string("input_section_3_subtitle") }
    static var inputQuickVehiclesSubtitle: String { string("input_quick_vehicles_subtitle") }
    static var inputAdvancedDetailsTitle: String { string("input_advanced_details_title") }
    static var inputSection4Title: String { string("input_section_4_title") }
    static var inputSection4Subtitle: String { string("input_section_4_subtitle") }
    static var fuelPriceLabel: String { string("fuel_price_label") }
    static var electricityPriceLabel: String { string("electricity_price_label") }
    static var ownershipYearsLabel: String { string("ownership_years_label") }
    static var yearSingular: String { string("year_singular") }
    static var yearPlural: String { string("year_plural") }
    static var areaTypeLabel: String { string("area_type_label") }
    static var areaTypeUrban: String { string("area_type_urban") }
    static var areaTypeMixed: String { string("area_type_mixed") }
    static var areaTypeUrbanDescription: String { string("area_type_urban_description") }
    static var areaTypeMixedDescription: String { string("area_type_mixed_description") }
    static var sourceVehicleLabel: String { string("source_vehicle_label") }
    static var targetVehicleLabel: String { string("target_vehicle_label") }
    static var sourceVehicleDescription: String { string("source_vehicle_description") }
    static var targetVehicleDescription: String { string("target_vehicle_description") }
    static var powertrainICE: String { string("powertrain_ice") }
    static var powertrainEV: String { string("powertrain_ev") }
    static var powertrainPHEV: String { string("powertrain_phev") }
    static var currentVehicleShort: String { string("current_vehicle_short") }
    static var electrifiedVehicleShort: String { string("electrified_vehicle_short") }
    static var comparisonCardTitle: String { string("comparison_card_title") }
    static var vehicleSearchPlaceholder: String { string("vehicle_search_placeholder") }
    static var vehiclePickerButton: String { string("vehicle_picker_button") }
    static var vehiclePickerSearchTitle: String { string("vehicle_picker_search_title") }
    static var vehiclePickerMinCharsHint: String { string("vehicle_picker_min_chars_hint") }
    static var vehiclePickerNoResults: String { string("vehicle_picker_no_results") }
    static var vehiclePickerTryDifferent: String { string("vehicle_picker_try_different") }
    static var vehiclePickerClose: String { string("vehicle_picker_close") }
    static var vehiclePickerClear: String { string("vehicle_picker_clear") }
    static var vehiclePickerPopularBrands: String { string("vehicle_picker_popular_brands") }
    static var vehiclePickerChooseYear: String { string("vehicle_picker_choose_year") }
    static var vehiclePickerResultsCapped: String { string("vehicle_picker_results_capped") }
    static var vehiclePairSectionTitle: String { string("vehicle_pair_section_title") }
    static var vehiclePairTapToChoose: String { string("vehicle_pair_tap_to_choose") }
    static var vehiclePickerTabBrowse: String { string("vehicle_picker_tab_browse") }
    static var vehiclePickerTabSearch: String { string("vehicle_picker_tab_search") }
    static var vehiclePickerBrowseSubtitle: String { string("vehicle_picker_browse_subtitle") }
    static var vehiclePickerBackBrands: String { string("vehicle_picker_back_brands") }
    static var vehiclePickerBrandModelsSubtitle: String { string("vehicle_picker_brand_models_subtitle") }
    static var vehiclePickerFilterBrandsPlaceholder: String { string("vehicle_picker_filter_brands_placeholder") }
    static var vehicleIceCompact: String { string("vehicle_ice_compact") }
    static var vehicleIceSuv: String { string("vehicle_ice_suv") }
    static var vehicleEvCompact: String { string("vehicle_ev_compact") }
    static var vehicleEvSuv: String { string("vehicle_ev_suv") }
    static var vehicleNotSelected: String { string("vehicle_not_selected") }
    static var vehicleDimensionsLabel: String { string("vehicle_dimensions_label") }
    static var vehicleDimensionsNotSelected: String { string("vehicle_dimensions_not_selected") }
    static func vehicleDimensionsFormat(_ length: Double, _ width: Double, _ height: Double) -> String {
        format("vehicle_dimensions_format", length, width, height)
    }
    static func vehicleComparisonDimensions(_ from: String, _ to: String) -> String {
        format("vehicle_comparison_dimensions", from, to)
    }
    static var externalDimensionsLinkTitle: String { string("external_dimensions_link_title") }
    static var externalDimensionsLinkSubtitle: String { string("external_dimensions_link_subtitle") }
    static var externalDimensionsLinkA11yHint: String { string("external_dimensions_link_a11y_hint") }
    /// URL confronto dimensioni (sito esterno; uso leggero senza incorporare contenuti).
    static var externalAutomobileDimensionsComparisonURL: URL {
        URL(string: "https://www.automobiledimension.com/car-comparison.php")!
    }
    static var homeChargingToggle: String { string("home_charging_toggle") }
    static var chargingTypeHome: String { string("charging_type_home") }
    static var chargingTypeHomeDescription: String { string("charging_type_home_description") }
    static var chargingTypePublicSlow: String { string("charging_type_public_slow") }
    static var chargingTypePublicSlowDescription: String { string("charging_type_public_slow_description") }
    static var chargingTypePublicFast: String { string("charging_type_public_fast") }
    static var chargingTypePublicFastDescription: String { string("charging_type_public_fast_description") }
    static var chargingTypePublicUltraFast: String { string("charging_type_public_ultra_fast") }
    static var chargingTypePublicUltraFastDescription: String { string("charging_type_public_ultra_fast_description") }
    static var tellMeTheTruth: String { string("tell_me_the_truth") }
    static var simulateCtaA11yHint: String { string("simulate_cta_a11y_hint") }
    
    // MARK: - Verdict
    static var modifyInput: String { string("modify_input") }
    static var modifyInputA11yHint: String { string("modify_input_a11y_hint") }
    static var shareResult: String { string("share_result") }
    static var exportPDFReport: String { string("export_pdf_report") }
    static var sharePDFReport: String { string("share_pdf_report") }
    static var freeReportTitle: String { string("free_report_title") }
    static var freeReportSubtitle: String { string("free_report_subtitle") }
    static var freeReportBadge: String { string("free_report_badge") }
    static var exportPDFA11yHint: String { string("export_pdf_a11y_hint") }
    static var talkToAdvisorA11yHint: String { string("talk_to_advisor_a11y_hint") }
    static var onboardingSkipA11yHint: String { string("onboarding_skip_a11y_hint") }
    static var guideOpenA11yHint: String { string("guide_open_a11y_hint") }
    static var privacyOpenA11yHint: String { string("privacy_open_a11y_hint") }
    static var fearEyebrow: String { string("fear_eyebrow") }
    static var realityEyebrow: String { string("reality_eyebrow") }
    static var pickerYearOne: String { string("picker_year_one") }
    static func pickerYearMany(_ n: Int) -> String { format("picker_year_many", n) }
    static var chartSeries: String { string("chart_series") }
    static var talkToAdvisor: String { string("talk_to_advisor") }
    static var leadSheetTitle: String { string("lead_sheet_title") }
    static var leadSheetSubtitle: String { string("lead_sheet_subtitle") }
    static var leadNamePlaceholder: String { string("lead_name_placeholder") }
    static var leadEmailPlaceholder: String { string("lead_email_placeholder") }
    static var leadCityPlaceholder: String { string("lead_city_placeholder") }
    static var leadConsentText: String { string("lead_consent_text") }
    static var leadSend: String { string("lead_send") }
    static var reportIncluded1: String { string("report_included_1") }
    static var reportIncluded2: String { string("report_included_2") }
    static var reportIncluded3: String { string("report_included_3") }
    static var verdictYes: String { string("verdict_yes") }
    static var verdictMaybe: String { string("verdict_maybe") }
    static var verdictNotYet: String { string("verdict_not_yet") }
    static var verdictYesTitle: String { string("verdict_yes_title") }
    static var verdictMaybeTitle: String { string("verdict_maybe_title") }
    static var verdictNotYetTitle: String { string("verdict_not_yet_title") }
    static var verdictYesDescription: String { string("verdict_yes_description") }
    static var verdictMaybeDescription: String { string("verdict_maybe_description") }
    static var verdictNotYetDescription: String { string("verdict_not_yet_description") }
    static var verdictSubtitleYes: String { string("verdict_subtitle_yes") }
    static var verdictSubtitleMaybe: String { string("verdict_subtitle_maybe") }
    static var verdictSubtitleNotYet: String { string("verdict_subtitle_not_yet") }
    static var why: String { string("why") }
    static var whatThisMeans: String { string("what_this_means") }
    static func impactSaveBetween(_ min: Int, _ max: Int) -> String { format("impact_save_between", min, max) }
    static func impactChargePerWeek(_ count: Int) -> String { format("impact_charge_per_week", count) }
    static var impactGasCostMore: String { string("impact_gas_cost_more") }
    static var shareSubject: String { string("share_subject") }
    static var shareMessage: String { string("share_message") }
    
    // MARK: - Onboarding
    static var getStarted: String { string("get_started") }
    static var onboardingTitle: String { string("onboarding_title") }
    static var onboardingSubtitle: String { string("onboarding_subtitle") }
    static var onboardingRowKm: String { string("onboarding_row_km") }
    static var onboardingRowChart: String { string("onboarding_row_chart") }
    static var onboardingRowFear: String { string("onboarding_row_fear") }
    
    // MARK: - Education / Fear vs Reality
    static var fearVsReality: String { string("fear_vs_reality") }
    static var commonFears: String { string("common_fears") }
    
    // MARK: - Comparison
    static var comparison5Year: String { string("comparison_5_year") }
    static func yearFormat(_ n: Int) -> String { format("year_format", n) }
    static var deepDiveCosts: String { string("deep_dive_costs") }
    static var deepDiveCostsClosed: String { string("deep_dive_costs_closed") }
    static var deepDiveCostsExplanation: String { string("deep_dive_costs_explanation") }
    static var deepDiveCostsTakeaway: String { string("deep_dive_costs_takeaway") }
    static var calculationExplanation: String { string("calculation_explanation") }
    static var calculationGasTitle: String { string("calculation_gas_title") }
    static func calculationGasFormula(
        _ km: Int,
        _ litersPerKm: Double,
        _ price: Double,
        _ energyCost: Double,
        _ yearlyCost: Double
    ) -> String {
        format("calculation_gas_formula", km, litersPerKm, price, energyCost, yearlyCost)
    }
    static func calculationGasTotal(_ years: Int, _ total: Int) -> String { format("calculation_gas_total", years, total) }
    static func calculationOpexBreakdown(
        _ energy: Double,
        _ maintenance: Double,
        _ taxes: Double,
        _ insurance: Double,
        _ yearlyCost: Double
    ) -> String {
        format("calculation_opex_breakdown", energy, maintenance, taxes, insurance, yearlyCost)
    }
    static var calculationEvTitle: String { string("calculation_ev_title") }
    static func calculationEvFormula(
        _ km: Int,
        _ kWhPerKm: Double,
        _ pricePerKWh: Double,
        _ energyCost: Double,
        _ yearlyCost: Double
    ) -> String {
        format("calculation_ev_formula", km, kWhPerKm, pricePerKWh, energyCost, yearlyCost)
    }
    static func calculationEvTotal(_ years: Int, _ total: Int) -> String { format("calculation_ev_total", years, total) }
    static func calculationChargingNote(_ weeklyCharges: Int) -> String {
        format("calculation_charging_note", weeklyCharges)
    }
    static func calculationSavings(_ years: Int, _ savings: Int) -> String { format("calculation_savings", years, savings) }
    static var savings: String { string("savings") }
    static var gasLabel: String { string("gas_label") }
    static var evLabel: String { string("ev_label") }
    
    // MARK: - Scenarios
    static var scenarioPessimistic: String { string("scenario_pessimistic") }
    static var scenarioRealistic: String { string("scenario_realistic") }
    static var scenarioOptimistic: String { string("scenario_optimistic") }
    static var scenarioTitle: String { string("scenario_title") }
    static var scenarioDescription: String { string("scenario_description") }
    static var scenarioDescriptionPessimistic: String { string("scenario_description_pessimistic") }
    static var scenarioDescriptionRealistic: String { string("scenario_description_realistic") }
    static var scenarioDescriptionOptimistic: String { string("scenario_description_optimistic") }
    
    // MARK: - Timeline Text
    static var timelinePessimistic1: String { string("timeline_pessimistic_1") }
    static var timelinePessimistic2: String { string("timeline_pessimistic_2") }
    static var timelinePessimistic3: String { string("timeline_pessimistic_3") }
    static var timelineRealistic1: String { string("timeline_realistic_1") }
    static var timelineRealistic2: String { string("timeline_realistic_2") }
    static var timelineRealistic3: String { string("timeline_realistic_3") }
    static var timelineOptimistic1: String { string("timeline_optimistic_1") }
    static var timelineOptimistic2: String { string("timeline_optimistic_2") }
    static var timelineOptimistic3: String { string("timeline_optimistic_3") }
    static var howItChangesOverTime: String { string("how_it_changes_over_time") }
    static var costsOverTime: String { string("costs_over_time") }
    static var costsOverTimeIntro: String { string("costs_over_time_intro") }
    static var costsChartTitle: String { string("costs_chart_title") }
    static var chartAxisOwnershipYear: String { string("chart_axis_ownership_year") }
    static var chartAxisCumulativeCost: String { string("chart_axis_cumulative_cost") }
    static var costsChartFootnote: String { string("costs_chart_footnote") }
    static var timeYear1: String { string("time_year1") }
    static var timeYear3: String { string("time_year3") }
    static var timeYear5: String { string("time_year5") }
    static var timeMessage: String { string("time_message") }
    
    // MARK: - Approfondimenti (Deep dive)
    static var deepDiveSectionTitle: String { string("deep_dive_section_title") }
    static var deepDiveSectionClosed: String { string("deep_dive_section_closed") }
    static var subsectionWhereNumbersTitle: String { string("subsection_where_numbers_title") }
    static var subsectionWhereNumbersBody: String { string("subsection_where_numbers_body") }
    static var subsectionEnvironmentTitle: String { string("subsection_environment_title") }
    static var subsectionEnvironmentBody: String { string("subsection_environment_body") }
    static var subsectionBatteryTitle: String { string("subsection_battery_title") }
    static var subsectionBatteryBody: String { string("subsection_battery_body") }
    static var subsectionIncentivesTitle: String { string("subsection_incentives_title") }
    static var subsectionIncentivesBody: String { string("subsection_incentives_body") }
    static var incentivesLinkTitle: String { string("incentives_link_title") }
    
    // MARK: - Assumptions & Transparency
    static var assumptionsTransparency: String { string("assumptions_transparency") }
    static var assumptionCalculationsEstimates: String { string("assumption_calculations_estimates") }
    static var assumptionNoDataSent: String { string("assumption_no_data_sent") }
    static var assumptionAveragePrices: String { string("assumption_average_prices") }
    static var assumptionConsumptionGas: String { string("assumption_consumption_gas") }
    static var assumptionConsumptionEv: String { string("assumption_consumption_ev") }
    static var assumptionMaintenance: String { string("assumption_maintenance") }
    static var assumptionTaxes: String { string("assumption_taxes") }
    static var assumptionElectricity: String { string("assumption_electricity") }
    
    // MARK: - Common Fears
    static func commonFearsBadge(_ count: Int) -> String { format("common_fears_badge", count) }
    
    // MARK: - Loading
    static var calculating: String { string("calculating") }
    static var calculatingSubtitle: String { string("calculating_subtitle") }

    // MARK: - Verdict proof (reference quality)
    static func verdictCompareLine(_ from: String, _ to: String) -> String {
        format("verdict_compare_line", from, to)
    }
    static func verdictProofSavingsValue(_ min: Int, _ max: Int) -> String {
        format("verdict_proof_savings_value", min, max)
    }
    static var verdictProofSavingsLabel: String { string("verdict_proof_savings_label") }
    static var verdictProofChargesLabel: String { string("verdict_proof_charges_label") }
    static func verdictProofBreakEvenValue(_ months: Int) -> String {
        format("verdict_proof_breakeven_value", months)
    }
    static var verdictProofBreakEvenLabel: String { string("verdict_proof_breakeven_label") }
    static var verdictTrustStrip: String { string("verdict_trust_strip") }
    static var shareCardEyebrow: String { string("share_card_eyebrow") }
    static var shareCardWeekShort: String { string("share_card_week_short") }
    
    // MARK: - Validation
    static var validationMinKm: String { string("validation_min_km") }
    static var validationMaxKm: String { string("validation_max_km") }
    static var validationSourceVehicleRequired: String { string("validation_source_vehicle_required") }
    static var validationTargetVehicleRequired: String { string("validation_target_vehicle_required") }
    static var validationFuelPositive: String { string("validation_fuel_positive") }
    static var validationFuelHigh: String { string("validation_fuel_high") }
    static var validationElectricityPositive: String { string("validation_electricity_positive") }
    static var validationElectricityHigh: String { string("validation_electricity_high") }
    static var validationMissingFuelConsumption: String { string("validation_missing_fuel_consumption") }
    static var validationMissingEnergyConsumption: String { string("validation_missing_energy_consumption") }
    static var validationUnknownSourceVehicle: String { string("validation_unknown_source_vehicle") }
    static var validationUnknownTargetVehicle: String { string("validation_unknown_target_vehicle") }
    static var validationMinYears: String { string("validation_min_years") }
    static var validationMaxYears: String { string("validation_max_years") }
    static var checkInputValues: String { string("check_input_values") }
    
    // MARK: - Simulator (reasons & fear/reality)
    static func chargePerWeek(_ n: Int) -> String { format("charge_per_week", n) }
    static func saveUpToPerYear(_ n: Int) -> String { format("save_up_to_per_year", n) }
    static func switchingFromTo(_ from: String, _ to: String) -> String { format("switching_from_to", from, to) }
    static var homeChargingEasier: String { string("home_charging_easier") }
    static var publicChargingManageable: String { string("public_charging_manageable") }
    static var fearRunOutBattery: String { string("fear_run_out_battery") }
    static var realityChargingFewTimes: String { string("reality_charging_few_times") }
    static var fearChargingComplicated: String { string("fear_charging_complicated") }
    static var realityPublicCharging: String { string("reality_public_charging") }
    static var fearEvsUnreliable: String { string("fear_evs_unreliable") }
    static var realityFewerParts: String { string("reality_fewer_parts") }
    static var fearCostsTooMuch: String { string("fear_costs_too_much") }
    static func realitySavePerYear(_ min: Int, _ max: Int) -> String { format("reality_save_per_year", min, max) }
    
    // MARK: - Share
    static var shareTitle: String { string("share_title") }
    static var shareVerdictYes: String { string("share_verdict_yes") }
    static var shareVerdictMaybe: String { string("share_verdict_maybe") }
    static var shareVerdictNotYet: String { string("share_verdict_not_yet") }
    static func shareWeeklyCharges(_ n: Int) -> String { format("share_weekly_charges", n) }
    static func shareYearlySavings(_ min: Int, _ max: Int) -> String { format("share_yearly_savings", min, max) }
    static var shareKeyReasons: String { string("share_key_reasons") }
    static var shareSignature: String { string("share_signature") }

    // MARK: - Shell & guides
    static var shellEditionMark: String { string("shell_edition_mark") }
    static var shellTaglineWorkshop: String { string("shell_tagline_workshop") }
    static var shellTaglineGuides: String { string("shell_tagline_guides") }
    static var shellTabWorkshop: String { string("shell_tab_workshop") }
    static var shellTabGuides: String { string("shell_tab_guides") }
    static var shellTabWorkshopA11yHint: String { string("shell_tab_workshop_a11y_hint") }
    static var shellTabGuidesA11yHint: String { string("shell_tab_guides_a11y_hint") }
    static var verdictModalTitle: String { string("verdict_modal_title") }
    static var verdictModalSubtitle: String { string("verdict_modal_subtitle") }
    static var verdictModalCloseA11y: String { string("verdict_modal_close_a11y") }
    static func verdictHeaderA11yLabel(resultTitle: String) -> String {
        format("verdict_header_a11y", resultTitle)
    }
    static var guidesHubTitle: String { string("guides_hub_title") }
    static var guidesHubIntro: String { string("guides_hub_intro") }
    static var guidesCardTapHint: String { string("guides_card_tap_hint") }
    static var guidesCardA11yHint: String { string("guides_card_a11y_hint") }
    static var guidesSheetClose: String { string("guides_sheet_close") }
    static var guideTopicRangeTitle: String { string("guide_topic_range_title") }
    static var guideTopicRangeBody: String { string("guide_topic_range_body") }
    static var guideTopicChargingTitle: String { string("guide_topic_charging_title") }
    static var guideTopicChargingBody: String { string("guide_topic_charging_body") }
    static var guideTopicBatteryTitle: String { string("guide_topic_battery_title") }
    static var guideTopicBatteryBody: String { string("guide_topic_battery_body") }
    static var guideTopicTotalCostTitle: String { string("guide_topic_total_cost_title") }
    static var guideTopicTotalCostBody: String { string("guide_topic_total_cost_body") }

    // MARK: - Accessibility (extra)
    static var expandableA11yHint: String { string("expandable_a11y_hint") }
    static var expandableA11yExpanded: String { string("expandable_a11y_expanded") }
    static var expandableA11yCollapsed: String { string("expandable_a11y_collapsed") }
    static var validationA11yTitle: String { string("validation_a11y_title") }
    static var vehiclePickerTabsA11yHint: String { string("vehicle_picker_tabs_a11y_hint") }
    static var vehiclePickerBrandA11yHint: String { string("vehicle_picker_brand_a11y_hint") }
    static var vehiclePickerSelectA11yHint: String { string("vehicle_picker_select_a11y_hint") }
    static var shareLinkA11yHint: String { string("share_link_a11y_hint") }
    static var fearVsRealityA11yFearPrefix: String { string("fear_vs_reality_a11y_fear_prefix") }
    static var fearVsRealityA11yRealityPrefix: String { string("fear_vs_reality_a11y_reality_prefix") }
    static var costsChartA11ySummary: String { string("costs_chart_a11y_summary") }
    static var costsChartA11yHint: String { string("costs_chart_a11y_hint") }
    static var scenarioChipA11yHint: String { string("scenario_chip_a11y_hint") }
    static var incentivesLinkA11yHint: String { string("incentives_link_a11y_hint") }
    static var vehiclePickerBackA11yHint: String { string("vehicle_picker_back_a11y_hint") }

    // MARK: - AI verdict explanation
    static var verdictAISectionTitle: String { string("verdict_ai_section_title") }
    static func verdictAIFallbackYes(_ km: Int, _ min: Int, _ max: Int, _ charges: Int) -> String {
        format("verdict_ai_fallback_yes", km, min, max, charges)
    }
    static func verdictAIFallbackMaybe(_ km: Int, _ min: Int, _ max: Int) -> String {
        format("verdict_ai_fallback_maybe", km, min, max)
    }
    static func verdictAIFallbackNotYet(_ km: Int, _ charges: Int) -> String {
        format("verdict_ai_fallback_not_yet", km, charges)
    }

    // MARK: - Break-even
    static func breakEvenMonthsReason(_ months: Int) -> String { format("break_even_months_reason", months) }
    static var breakEvenNotReachedReason: String { string("break_even_not_reached_reason") }
    static func breakEvenMonthsBadge(_ months: Int) -> String { format("break_even_months_badge", months) }
    static var openLastVerdictDialog: String { string("open_last_verdict_dialog") }

    // MARK: - Trip / purchase / incentives / history / sources / OCR / PDF
    static var tripProfileLabel: String { string("trip_profile_label") }
    static var tripProfileCustom: String { string("trip_profile_custom") }
    static var tripProfileCommuter: String { string("trip_profile_commuter") }
    static var tripProfileWeekend: String { string("trip_profile_weekend") }
    static var tripProfileCustomSubtitle: String { string("trip_profile_custom_subtitle") }
    static var tripProfileCommuterSubtitle: String { string("trip_profile_commuter_subtitle") }
    static var tripProfileWeekendSubtitle: String { string("trip_profile_weekend_subtitle") }
    static var purchasePricesTitle: String { string("purchase_prices_title") }
    static var sourcePurchasePriceLabel: String { string("source_purchase_price_label") }
    static var targetPurchasePriceLabel: String { string("target_purchase_price_label") }
    static var includeIncentivesToggle: String { string("include_incentives_toggle") }
    static var includeIncentivesHint: String { string("include_incentives_hint") }
    static func incentivesIncludedReason(_ euro: Int) -> String { format("incentives_included_reason", euro) }
    static var incentivesTransparencyNote: String { string("incentives_transparency_note") }
    static var sourcesSectionTitle: String { string("sources_section_title") }
    static var sourceCatalogNote: String { string("source_catalog_note") }
    static var sourcePricesNote: String { string("source_prices_note") }
    static var historySectionTitle: String { string("history_section_title") }
    static var historyEmpty: String { string("history_empty") }
    static var historyClosedHint: String { string("history_closed_hint") }
    static var stickerScanTitle: String { string("sticker_scan_title") }
    static var stickerScanButton: String { string("sticker_scan_button") }
    static var stickerScanHint: String { string("sticker_scan_hint") }
    static var stickerScanFoundFuel: String { string("sticker_scan_found_fuel") }
    static var stickerScanFoundEnergy: String { string("sticker_scan_found_energy") }
    static var stickerScanNothing: String { string("sticker_scan_nothing") }
    static var quickStartTitle: String { string("quick_start_title") }
    static var quickStartSubtitle: String { string("quick_start_subtitle") }
    static var quickStartContinue: String { string("quick_start_continue") }
    static var quickStartSkipFull: String { string("quick_start_skip_full") }
    static var widgetBumpFuelTitle: String { string("widget_bump_fuel_title") }
    static var stickerOverrideAppliedReason: String { string("sticker_override_applied_reason") }
    static var stickerClearOverride: String { string("sticker_clear_override") }
    static var historyRestoreHint: String { string("history_restore_hint") }
    static var validationPurchaseTooLow: String { string("validation_purchase_too_low") }
    static var validationPurchaseTooHigh: String { string("validation_purchase_too_high") }
    static var validationStickerFuelRange: String { string("validation_sticker_fuel_range") }
    static var validationStickerEnergyRange: String { string("validation_sticker_energy_range") }
    static func yearlyKmValue(_ km: Int) -> String { format("yearly_km_value", km) }
    static var phevBlendReason: String { string("phev_blend_reason") }
    static var insuranceIncludedReason: String { string("insurance_included_reason") }
    static var leadSavedLocally: String { string("lead_saved_locally") }
    static var leadSentRemote: String { string("lead_sent_remote") }
    static var leadSendFailed: String { string("lead_send_failed") }
    static var tcoExtrasTitle: String { string("tco_extras_title") }
    static var tcoExtrasClosed: String { string("tco_extras_closed") }
    static var tcoExtrasIntro: String { string("tco_extras_intro") }
    static func tcoInsuranceRow(_ ice: Int, _ ev: Int) -> String { format("tco_insurance_row", ice, ev) }
    static func tcoResidualRow(_ years: Int, _ ice: Int, _ ev: Int) -> String { format("tco_residual_row", years, ice, ev) }
    static var tcoResidualNote: String { string("tco_residual_note") }
    static var pricesFreshJustNow: String { string("prices_fresh_just_now") }
    static func pricesFreshMinutesAgo(_ minutes: Int) -> String { format("prices_fresh_minutes_ago", minutes) }
    static var pricesFreshCached: String { string("prices_fresh_cached") }
    static var pricesFreshBundled: String { string("prices_fresh_bundled") }
    static var liveActivityClear: String { string("live_activity_clear") }

    // MARK: - App Intents
    static var intentSimulateDescription: String { string("intent_simulate_description") }
    static var intentOpenVerdictDescription: String { string("intent_open_verdict_description") }

    // MARK: - Input a11y
    static var yearlyKmSliderA11y: String { string("yearly_km_slider_a11y") }
    static var fuelPriceSliderA11y: String { string("fuel_price_slider_a11y") }
    static var electricityPriceSliderA11y: String { string("electricity_price_slider_a11y") }
    static var areaTypePickerA11y: String { string("area_type_picker_a11y") }
    static var homeChargingA11y: String { string("home_charging_a11y") }

    // MARK: - Errors
    static var errorNetworkUnavailable: String { string("error_network_unavailable") }
    static var errorNetworkTimeout: String { string("error_network_timeout") }
    static var errorInvalidURL: String { string("error_invalid_url") }
    static var errorServerError: String { string("error_server_error") }
    static var errorNoDataReceived: String { string("error_no_data_received") }
    static var errorDataCorrupted: String { string("error_data_corrupted") }
    static var errorDataNotFound: String { string("error_data_not_found") }
    static var errorInvalidDataFormat: String { string("error_invalid_data_format") }
    static var errorParsing: String { string("error_parsing") }
    static var errorCatalogLoadFailed: String { string("error_catalog_load_failed") }
    static var errorCatalogParseFailed: String { string("error_catalog_parse_failed") }
    static var errorVehicleNotFound: String { string("error_vehicle_not_found") }
    static var errorCatalogOutOfDate: String { string("error_catalog_out_of_date") }
    static var errorStorageReadFailed: String { string("error_storage_read_failed") }
    static var errorStorageWriteFailed: String { string("error_storage_write_failed") }
    static var errorStorageCorrupted: String { string("error_storage_corrupted") }
    static var errorServiceUnavailable: String { string("error_service_unavailable") }
    static var errorConfiguration: String { string("error_configuration") }
    static var errorFuelPriceFetchFailed: String { string("error_fuel_price_fetch_failed") }
    static var errorElectricityPriceFetchFailed: String { string("error_electricity_price_fetch_failed") }
    static var errorCostServiceUnavailable: String { string("error_cost_service_unavailable") }
    static var errorUnknown: String { string("error_unknown") }
    static var errorTitleGeneral: String { string("error_title_general") }
    static var errorTitleNetwork: String { string("error_title_network") }
    static var errorTitleData: String { string("error_title_data") }
    static var errorTitleCatalog: String { string("error_title_catalog") }
    static var errorTitleValidation: String { string("error_title_validation") }
    static var retry: String { string("retry") }
    static var dismiss: String { string("dismiss") }
    static var suggestionCheckConnection: String { string("suggestion_check_connection") }
    static var suggestionRetryLater: String { string("suggestion_retry_later") }
    static var suggestionSelectAnotherVehicle: String { string("suggestion_select_another_vehicle") }
    static var suggestionReinstallApp: String { string("suggestion_reinstall_app") }
    static var suggestionContactSupport: String { string("suggestion_contact_support") }

    // MARK: - Privacy
    static var privacyPolicyTitle: String { string("privacy_policy_title") }
    static var privacyPolicyUpdated: String { string("privacy_policy_updated") }
    static var privacyPolicyBody: String { string("privacy_policy_body") }
    static var privacyPolicyOpenWeb: String { string("privacy_policy_open_web") }
}

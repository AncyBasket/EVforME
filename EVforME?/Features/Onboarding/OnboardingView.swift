//
//  OnboardingView.swift
//  EVforME?
//

import SwiftUI

struct OnboardingView: View {
    @Binding var userInput: UserInput
    var onContinue: () -> Void
    var onSkip: () -> Void

    @State private var appeared = false
    @StateObject private var marketResolver = MarketLocationResolver()
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    var body: some View {
        ZStack {
            ImmersiveBackground()

            VStack(spacing: 0) {
                HStack {
                    Spacer()
                    Button(L10n.quickStartSkipFull, action: onSkip)
                        .font(Typography.readingCaption.weight(.semibold))
                        .foregroundStyle(Color.secondaryText)
                        .padding(.trailing, 22)
                        .padding(.top, 14)
                        .accessibilityHint(L10n.onboardingSkipA11yHint)
                }

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 28) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text(L10n.appTitle)
                                .font(Typography.display)
                                .foregroundStyle(Color.ink)

                            Text(L10n.quickStartTitle)
                                .font(Typography.readingIntro)
                                .foregroundStyle(Color.secondaryText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(.top, 20)

                        marketSection

                        VStack(alignment: .leading, spacing: 10) {
                            Text(L10n.dailyKmQuestion)
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.secondaryText)
                                .tracking(0.6)
                            Text(L10n.yearlyKmValue(userInput.dailyKm))
                                .font(Typography.metric)
                                .foregroundStyle(Color.ink)
                            Slider(
                                value: Binding(
                                    get: { Double(userInput.dailyKm) },
                                    set: {
                                        userInput.dailyKm = Int($0.rounded())
                                        if userInput.tripProfile != .custom {
                                            userInput.tripProfile = .custom
                                        }
                                    }
                                ),
                                in: 1000...120_000,
                                step: 500
                            )
                            .tint(Color.ink)
                        }

                        VStack(alignment: .leading, spacing: 10) {
                            Text(L10n.homeChargingToggle)
                                .font(Typography.sectionEyebrow)
                                .foregroundStyle(Color.secondaryText)
                                .tracking(0.6)
                            Toggle(isOn: $userInput.hasHomeCharging) {
                                Text(L10n.homeChargingToggle)
                                    .font(Typography.title2)
                                    .foregroundStyle(Color.ink)
                            }
                            .tint(Color.accentDark)
                            .labelsHidden()
                            .accessibilityLabel(L10n.homeChargingA11y)
                        }

                        Text(L10n.quickStartSubtitle)
                            .font(Typography.readingCaption)
                            .foregroundStyle(Color.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)

                        Spacer(minLength: 40)
                    }
                    .padding(.horizontal, 24)
                    .opacity(appeared ? 1 : 0)
                    .offset(y: appeared ? 0 : 16)
                }

                PrimaryButton(title: L10n.quickStartContinue, action: onContinue)
                    .padding(.horizontal, 24)
                    .padding(.bottom, 28)
                    .padding(.top, 8)
            }
        }
        .onAppear {
            if accessibilityReduceMotion {
                appeared = true
            } else {
                withAnimation(.spring(response: 0.55, dampingFraction: 0.88)) {
                    appeared = true
                }
            }
        }
        .onChange(of: marketResolver.status) { _, newStatus in
            if case .ready(let market) = newStatus {
                userInput.market = market
            }
        }
    }

    private var marketSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(L10n.marketSectionTitle)
                .font(Typography.sectionEyebrow)
                .foregroundStyle(Color.secondaryText)
                .tracking(0.6)

            Text(L10n.marketSectionSubtitle)
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)

            Picker(L10n.marketPickerLabel, selection: $userInput.market) {
                ForEach(AppMarket.pickerCases) { market in
                    Text(market.localizedName).tag(market)
                }
            }
            .pickerStyle(.menu)
            .tint(Color.ink)

            Button {
                marketResolver.resolveMarketFromLocation()
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "location.fill")
                    Text(locationButtonTitle)
                        .font(Typography.readingCaption.weight(.semibold))
                }
                .foregroundStyle(Color.ink)
                .padding(.vertical, 10)
                .padding(.horizontal, 14)
                .background(Color.surfaceElevated.opacity(0.9))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
            .accessibilityHint(L10n.marketLocationA11yHint)

            if let statusNote = locationStatusNote {
                Text(statusNote)
                    .font(Typography.readingCaption)
                    .foregroundStyle(Color.secondaryText)
            }

            Text(L10n.marketMaintenanceSource(userInput.market))
                .font(Typography.readingCaption)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var locationButtonTitle: String {
        switch marketResolver.status {
        case .requestingPermission, .locating, .resolvingCountry:
            return L10n.marketLocationWorking
        default:
            return L10n.marketUseLocation
        }
    }

    private var locationStatusNote: String? {
        switch marketResolver.status {
        case .ready(let market):
            return L10n.marketLocationDetected(market.localizedName)
        case .denied:
            return L10n.marketLocationDenied
        case .failed, .timedOut:
            return L10n.marketLocationFailed
        default:
            return nil
        }
    }
}

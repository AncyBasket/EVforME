//
//  GuidesHubView.swift
//  EVforME?
//

import SwiftUI

private enum GuideTopic: Int, Identifiable, CaseIterable {
    case range = 0
    case charging
    case battery
    case totalCost

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .range: return L10n.guideTopicRangeTitle
        case .charging: return L10n.guideTopicChargingTitle
        case .battery: return L10n.guideTopicBatteryTitle
        case .totalCost: return L10n.guideTopicTotalCostTitle
        }
    }

    var body: String {
        switch self {
        case .range: return L10n.guideTopicRangeBody
        case .charging: return L10n.guideTopicChargingBody
        case .battery: return L10n.guideTopicBatteryBody
        case .totalCost: return L10n.guideTopicTotalCostBody
        }
    }
}

struct GuidesHubView: View {
    @State private var selectedTopic: GuideTopic?
    @State private var showPrivacy = false
    @State private var appeared = false
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text(L10n.appTitle)
                    .font(Typography.display)
                    .foregroundStyle(Color.ink)
                    .padding(.top, 8)

                Text(L10n.guidesHubIntro)
                    .font(Typography.readingIntro)
                    .foregroundStyle(Color.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(alignment: .leading, spacing: 0) {
                    ForEach(GuideTopic.allCases) { topic in
                        Button {
                            selectedTopic = topic
                        } label: {
                            HStack(alignment: .firstTextBaseline) {
                                Text(topic.title)
                                    .font(Typography.title2)
                                    .foregroundStyle(Color.ink)
                                    .multilineTextAlignment(.leading)
                                Spacer(minLength: 12)
                                Text("→")
                                    .font(.system(size: 18, weight: .medium, design: .serif))
                                    .foregroundStyle(Color.secondaryText)
                                    .accessibilityHidden(true)
                            }
                            .padding(.vertical, 18)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint(L10n.guideOpenA11yHint)

                        Rectangle()
                            .fill(Color.hairlineBorder)
                            .frame(height: 1)
                    }

                    Button {
                        showPrivacy = true
                    } label: {
                        HStack(alignment: .firstTextBaseline) {
                            Text(L10n.privacyPolicyTitle)
                                .font(Typography.title2)
                                .foregroundStyle(Color.ink)
                                .multilineTextAlignment(.leading)
                            Spacer(minLength: 12)
                            Text("→")
                                .font(.system(size: 18, weight: .medium, design: .serif))
                                .foregroundStyle(Color.secondaryText)
                                .accessibilityHidden(true)
                        }
                        .padding(.vertical, 18)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityHint(L10n.privacyOpenA11yHint)
                }
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 32)
            .opacity(appeared ? 1 : 0)
            .offset(y: appeared ? 0 : 12)
        }
        .scrollIndicators(.hidden)
        .onAppear {
            if accessibilityReduceMotion {
                appeared = true
            } else {
                withAnimation(.spring(response: 0.5, dampingFraction: 0.88)) {
                    appeared = true
                }
            }
        }
        .sheet(item: $selectedTopic) { topic in
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text(topic.title)
                            .font(Typography.readingTitle)
                            .foregroundStyle(Color.ink)
                        Text(topic.body)
                            .font(Typography.readingBody)
                            .foregroundStyle(Color.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(24)
                }
                .background(Color.appScreenBackground.ignoresSafeArea())
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(L10n.vehiclePickerClose) { selectedTopic = nil }
                    }
                }
            }
            .presentationDetents([.medium, .large])
        }
        .sheet(isPresented: $showPrivacy) {
            PrivacyPolicyView()
                .presentationDetents([.medium, .large])
        }
    }
}

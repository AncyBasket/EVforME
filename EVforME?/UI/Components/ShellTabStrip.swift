//
//  ShellTabStrip.swift
//  EVforME?
//

import SwiftUI

struct ShellTabStrip: View {
    @Binding var selection: AppShellTab
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    var body: some View {
        HStack(spacing: 0) {
            tabButton(.workshop, title: L10n.shellTabWorkshop, hint: L10n.shellTabWorkshopA11yHint)
            tabButton(.guides, title: L10n.shellTabGuides, hint: L10n.shellTabGuidesA11yHint)
        }
        .padding(.horizontal, 24)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(Color.hairlineBorder)
                .frame(height: 1)
        }
    }

    private func tabButton(_ tab: AppShellTab, title: String, hint: String) -> some View {
        let selected = selection == tab
        return Button {
            let animation: Animation = accessibilityReduceMotion
                ? .easeInOut(duration: 0.2)
                : .spring(response: 0.4, dampingFraction: 0.88)
            withAnimation(animation) {
                selection = tab
            }
            UISelectionFeedbackGenerator().selectionChanged()
        } label: {
            VStack(spacing: 6) {
                Text(title)
                    .font(Typography.readingCaption.weight(selected ? .bold : .medium))
                    .foregroundStyle(selected ? Color.ink : Color.secondaryText)
                Capsule()
                    .fill(selected ? Color.accent : Color.clear)
                    .frame(width: 28, height: 3)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityHint(hint)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

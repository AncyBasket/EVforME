//
//  ExpandableSection.swift
//  EVforME?
//

import SwiftUI

/// Capitolo editoriale: divider + titolo, niente card accordion.
struct ExpandableSection<Content: View>: View {
    let title: String
    let closedDescription: String?
    @State private var isExpanded: Bool = false
    @ViewBuilder let content: () -> Content
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    init(title: String, closedDescription: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.closedDescription = closedDescription
        self.content = content
    }

    private var toggleAnimation: Animation {
        accessibilityReduceMotion
            ? .easeInOut(duration: 0.16)
            : .spring(response: 0.38, dampingFraction: 0.86)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Rectangle()
                .fill(Color.hairlineBorder)
                .frame(height: 1)

            Button {
                UISelectionFeedbackGenerator().selectionChanged()
                withAnimation(toggleAnimation) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title)
                            .font(Typography.title2)
                            .foregroundColor(.ink)
                            .multilineTextAlignment(.leading)
                        if !isExpanded, let description = closedDescription {
                            Text(description)
                                .font(Typography.readingCaption)
                                .foregroundColor(.secondaryText)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    Spacer(minLength: 8)
                    Text(isExpanded ? "−" : "+")
                        .font(.system(size: 22, weight: .medium, design: .serif))
                        .foregroundStyle(Color.ink)
                        .frame(width: 28, alignment: .trailing)
                }
                .padding(.vertical, 18)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(title)
            .accessibilityHint(L10n.expandableA11yHint)
            .accessibilityValue(isExpanded ? L10n.expandableA11yExpanded : L10n.expandableA11yCollapsed)

            if isExpanded {
                content()
                    .padding(.bottom, 20)
                    .transition(.opacity)
            }
        }
    }
}

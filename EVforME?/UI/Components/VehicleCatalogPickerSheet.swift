//
//  VehicleCatalogPickerSheet.swift
//  EVforME?
//

import SwiftUI

/// Catalogo: ricerca unificata + marche popolari + modelli raggruppati (anno a parte).
struct VehicleCatalogPickerSheet: View {
    let title: String
    let vehicles: [VehicleCatalogItem]
    @Binding var selectedId: String
    @Environment(\.dismiss) private var dismiss

    private struct ModelGroup: Identifiable {
        let brand: String
        let model: String
        let variants: [VehicleCatalogItem]

        var id: String { "\(brand)|\(model)".lowercased() }

        var representative: VehicleCatalogItem {
            variants.first(where: { $0.heroImageURL != nil })
                ?? variants.max(by: { $0.year < $1.year })
                ?? variants[0]
        }

        var yearLabel: String {
            let years = variants.map(\.year)
            guard let minY = years.min(), let maxY = years.max() else { return "" }
            if minY == maxY { return "\(minY)" }
            return "\(minY)–\(maxY)"
        }

        var countLabel: String {
            variants.count == 1 ? L10n.pickerYearOne : L10n.pickerYearMany(variants.count)
        }
    }

    @State private var searchText: String = ""
    @State private var selectedBrand: String?
    @State private var selectedGroup: ModelGroup?
    @FocusState private var searchFocused: Bool
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    private static let maxGroups = 80
    private static let popularBrands = [
        "Fiat", "Volkswagen", "Toyota", "Renault", "Ford", "Peugeot",
        "BMW", "Audi", "Mercedes-Benz", "Tesla", "Hyundai", "Kia", "Nissan", "Opel",
    ]

    private var catalogAnimation: Animation {
        accessibilityReduceMotion ? .easeOut(duration: 0.16) : .easeOut(duration: 0.22)
    }

    private var query: String {
        searchText.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var availablePopularBrands: [String] {
        let present = Set(vehicles.map(\.brand))
        return Self.popularBrands.filter { present.contains($0) }
    }

    private var searchIndex: VehicleSearchIndex {
        VehicleSearchIndex(vehicles: vehicles)
    }

    private var visibleGroups: (rows: [ModelGroup], truncated: Bool) {
        let hits = searchIndex.search(
            query: searchText,
            brandFilter: selectedBrand,
            limit: Self.maxGroups + 1
        )
        let truncated = hits.count > Self.maxGroups
        let rows = Array(hits.prefix(Self.maxGroups)).map { hit in
            ModelGroup(brand: hit.brand, model: hit.model, variants: hit.variants)
        }
        return (rows, truncated)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ImmersiveBackground()

                if let group = selectedGroup {
                    yearPickerSurface(group)
                } else {
                    mainSurface
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L10n.vehiclePickerClose) { dismiss() }
                }
                if !selectedId.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button(L10n.vehiclePickerClear) { selectedId = "" }
                    }
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
        .onAppear {
            searchFocused = true
        }
    }

    // MARK: - Main

    private var mainSurface: some View {
        VStack(alignment: .leading, spacing: 12) {
            searchField
                .padding(.horizontal, 20)
                .padding(.top, 8)

            if query.isEmpty {
                popularBrandsRail
            }

            if let selectedBrand {
                HStack {
                    Button {
                        withAnimation(catalogAnimation) { self.selectedBrand = nil }
                    } label: {
                        Label(selectedBrand, systemImage: "xmark.circle.fill")
                            .font(Typography.readingCardTitle)
                            .foregroundColor(.accent)
                    }
                    .buttonStyle(.plain)
                    Spacer()
                }
                .padding(.horizontal, 20)
            }

            let outcome = visibleGroups
            if outcome.rows.isEmpty {
                ContentUnavailableView(
                    L10n.vehiclePickerNoResults,
                    systemImage: "car.side",
                    description: Text(L10n.vehiclePickerTryDifferent)
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(outcome.rows) { group in
                            modelGroupRow(group)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 28)

                    if outcome.truncated {
                        Text(L10n.vehiclePickerResultsCapped)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 20)
                            .padding(.bottom, 20)
                    }
                }
                .scrollDismissesKeyboard(.interactively)
            }
        }
    }

    private var searchField: some View {
        HStack(spacing: 12) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondaryText)
            TextField(L10n.vehicleSearchPlaceholder, text: $searchText)
                .font(Typography.readingBody)
                .focused($searchFocused)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.search)
            if !searchText.isEmpty {
                Button {
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Color.secondaryText)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 2, style: .continuous)
                .fill(Color.surfaceElevated.opacity(0.001))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 2, style: .continuous)
                .stroke(searchFocused ? Color.ink : Color.hairlineBorder, lineWidth: searchFocused ? 1.5 : 1)
        )
    }

    private var popularBrandsRail: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(L10n.vehiclePickerPopularBrands)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.horizontal, 20)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(availablePopularBrands, id: \.self) { brand in
                        Button {
                            UISelectionFeedbackGenerator().selectionChanged()
                            withAnimation(catalogAnimation) {
                                selectedBrand = brand
                                searchText = ""
                            }
                        } label: {
                            Text(brand)
                                .font(Typography.readingCaption.weight(.semibold))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 9)
                                .background(
                                    RoundedRectangle(cornerRadius: 2, style: .continuous)
                                        .fill(selectedBrand == brand ? Color.ctaFill : Color.clear)
                                )
                                .overlay(
                                    RoundedRectangle(cornerRadius: 2, style: .continuous)
                                        .stroke(Color.ink.opacity(selectedBrand == brand ? 0 : 0.25), lineWidth: 1)
                                )
                                .foregroundColor(selectedBrand == brand ? Color.ctaLabel : Color.ink)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 20)
            }
        }
    }

    private func modelGroupRow(_ group: ModelGroup) -> some View {
        Button {
            UISelectionFeedbackGenerator().selectionChanged()
            if group.variants.count == 1 {
                pick(group.variants[0])
            } else {
                withAnimation(catalogAnimation) {
                    selectedGroup = group
                }
            }
        } label: {
            HStack(spacing: 14) {
                VehicleHeroImage(
                    vehicle: group.representative,
                    height: 56,
                    cornerRadius: 2,
                    showsLabelsBelow: false,
                    squareThumbnail: true
                )

                VStack(alignment: .leading, spacing: 4) {
                    Text(group.brand)
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                    Text(group.model)
                        .font(Typography.title2)
                        .foregroundColor(.ink)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                    Text("\(group.yearLabel) · \(group.countLabel)")
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                Text(group.variants.count == 1 ? "✓" : "→")
                    .font(.system(size: 16, weight: .medium, design: .serif))
                    .foregroundColor(.secondaryText)
            }
            .padding(.vertical, 12)
            .overlay(alignment: .bottom) {
                Rectangle().fill(Color.hairlineBorder).frame(height: 1)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(group.brand) \(group.model), \(group.yearLabel)")
        .accessibilityHint(L10n.vehiclePickerSelectA11yHint)
    }

    // MARK: - Year picker

    private func yearPickerSurface(_ group: ModelGroup) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Button {
                    withAnimation(catalogAnimation) { selectedGroup = nil }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 14, weight: .semibold))
                        Text(L10n.vehiclePickerBackBrands)
                            .font(Typography.readingCardTitle)
                    }
                    .foregroundColor(.ink)
                }
                .buttonStyle(.plain)

                Text("\(group.brand) \(group.model)")
                    .font(Typography.readingCardTitle)
                    .foregroundColor(.primaryText)
                    .lineLimit(2)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 10)

            Text(L10n.vehiclePickerChooseYear)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)

            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(group.variants) { vehicle in
                        yearRow(vehicle)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 28)
            }
        }
    }

    private func yearRow(_ vehicle: VehicleCatalogItem) -> some View {
        Button {
            pick(vehicle)
        } label: {
            HStack(spacing: 14) {
                Text(String(vehicle.year))
                    .font(Typography.metric)
                    .foregroundColor(.ink)
                    .frame(width: 64, alignment: .leading)

                VStack(alignment: .leading, spacing: 2) {
                    Text(vehicle.dimensionsText)
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                        .lineLimit(1)
                    if let quality = vehicle.qualitySubtitle {
                        Text(quality)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText.opacity(0.85))
                            .lineLimit(1)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                if selectedId == vehicle.id {
                    Text("✓")
                        .font(.system(size: 18, weight: .bold, design: .serif))
                        .foregroundStyle(Color.ink)
                }
            }
            .padding(.vertical, 14)
            .overlay(alignment: .bottom) {
                Rectangle()
                    .fill(selectedId == vehicle.id ? Color.accent : Color.hairlineBorder)
                    .frame(height: selectedId == vehicle.id ? 2 : 1)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(vehicle.displayName)
    }

    private func pick(_ vehicle: VehicleCatalogItem) {
        selectedId = vehicle.id
        UISelectionFeedbackGenerator().selectionChanged()
        dismiss()
    }
}

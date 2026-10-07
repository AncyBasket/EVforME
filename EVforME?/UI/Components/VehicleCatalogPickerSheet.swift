//
//  VehicleCatalogPickerSheet.swift
//  EVforME?
//
//  Browse stile AutoScout: Marca → Modello → Anno/trim/alimentazione.
//

import SwiftUI

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
            variants.max(by: { $0.year < $1.year }) ?? variants[0]
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

    private enum BrowseLevel: Equatable {
        case brands
        case models(brand: String)
        case variants(brand: String, model: String)
    }

    @State private var searchText: String = ""
    @State private var level: BrowseLevel = .brands
    @FocusState private var searchFocused: Bool
    @Environment(\.accessibilityReduceMotion) private var accessibilityReduceMotion

    private static let maxSearchHits = 80
    private static let popularBrands = [
        "Fiat", "Volkswagen", "Toyota", "Renault", "Ford", "Peugeot",
        "BMW", "Audi", "Mercedes-Benz", "Tesla", "Hyundai", "Kia", "Nissan", "Opel", "SEAT",
    ]

    private var catalogAnimation: Animation {
        accessibilityReduceMotion ? .easeOut(duration: 0.16) : .easeOut(duration: 0.22)
    }

    private var query: String {
        searchText.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var searchIndex: VehicleSearchIndex {
        VehicleSearchIndex(vehicles: vehicles)
    }

    private var isSearching: Bool { !query.isEmpty }

    var body: some View {
        NavigationStack {
            ZStack {
                ImmersiveBackground()
                VStack(alignment: .leading, spacing: 12) {
                    searchField
                        .padding(.horizontal, 20)
                        .padding(.top, 8)

                    if isSearching {
                        searchResultsSurface
                    } else {
                        browseSurface
                    }
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
            searchFocused = false
        }
        .onChange(of: searchText) { _, newValue in
            if !newValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                // Ricerca libera: esci dal drill-down.
            }
        }
    }

    // MARK: - Search field

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
        .overlay(
            RoundedRectangle(cornerRadius: 2, style: .continuous)
                .stroke(searchFocused ? Color.ink : Color.hairlineBorder, lineWidth: searchFocused ? 1.5 : 1)
        )
    }

    // MARK: - Browse hierarchy

    @ViewBuilder
    private var browseSurface: some View {
        switch level {
        case .brands:
            brandListSurface
        case .models(let brand):
            modelListSurface(brand: brand)
        case .variants(let brand, let model):
            if let group = modelGroup(brand: brand, model: model) {
                variantListSurface(group)
            } else {
                brandListSurface
            }
        }
    }

    private var brandListSurface: some View {
        let brands = searchIndex.allBrands(popularFirst: Self.popularBrands)
        return VStack(alignment: .leading, spacing: 8) {
            Text(L10n.vehiclePickerBrowseSubtitle)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.horizontal, 20)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(brands, id: \.self) { brand in
                        Button {
                            UISelectionFeedbackGenerator().selectionChanged()
                            withAnimation(catalogAnimation) {
                                level = .models(brand: brand)
                            }
                        } label: {
                            HStack {
                                Text(brand)
                                    .font(Typography.title2)
                                    .foregroundColor(.ink)
                                Spacer()
                                Text("→")
                                    .font(.system(size: 16, weight: .medium, design: .serif))
                                    .foregroundColor(.secondaryText)
                            }
                            .padding(.vertical, 14)
                            .padding(.horizontal, 20)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint(L10n.vehiclePickerBrandA11yHint)

                        Rectangle()
                            .fill(Color.hairlineBorder)
                            .frame(height: 1)
                            .padding(.horizontal, 20)
                    }
                }
                .padding(.bottom, 28)
            }
        }
    }

    private func modelListSurface(brand: String) -> some View {
        let models = searchIndex.models(forBrand: brand)
        return VStack(alignment: .leading, spacing: 0) {
            backBar(title: L10n.vehiclePickerBackBrands) {
                level = .brands
            }

            Text(brand)
                .font(Typography.readingCardTitle)
                .foregroundColor(.primaryText)
                .padding(.horizontal, 20)
                .padding(.bottom, 4)

            Text(L10n.vehiclePickerBrandModelsSubtitle)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)

            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(models) { hit in
                        let group = ModelGroup(brand: hit.brand, model: hit.model, variants: hit.variants)
                        Button {
                            UISelectionFeedbackGenerator().selectionChanged()
                            withAnimation(catalogAnimation) {
                                level = .variants(brand: hit.brand, model: hit.model)
                            }
                        } label: {
                            HStack(spacing: 14) {
                                VehicleHeroImage(
                                    vehicle: group.representative,
                                    height: 52,
                                    cornerRadius: 2,
                                    showsLabelsBelow: false,
                                    squareThumbnail: true
                                )
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(group.model)
                                        .font(Typography.title2)
                                        .foregroundColor(.ink)
                                        .lineLimit(2)
                                    Text("\(group.yearLabel) · \(group.countLabel)")
                                        .font(Typography.readingCaption)
                                        .foregroundColor(.secondaryText)
                                }
                                Spacer()
                                Text("→")
                                    .foregroundColor(.secondaryText)
                            }
                            .padding(.vertical, 12)
                            .padding(.horizontal, 20)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(group.brand) \(group.model), \(group.yearLabel)")
                        .accessibilityHint(L10n.vehiclePickerSelectA11yHint)

                        Rectangle()
                            .fill(Color.hairlineBorder)
                            .frame(height: 1)
                            .padding(.horizontal, 20)
                    }
                }
                .padding(.bottom, 28)
            }
        }
    }

    private func variantListSurface(_ group: ModelGroup) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            backBar(title: L10n.vehiclePickerBackBrands) {
                level = .models(brand: group.brand)
            }

            Text("\(group.brand) \(group.model)")
                .font(Typography.readingCardTitle)
                .foregroundColor(.primaryText)
                .padding(.horizontal, 20)
                .padding(.bottom, 4)

            Text(L10n.vehiclePickerChooseYear)
                .font(Typography.readingCaption)
                .foregroundColor(.secondaryText)
                .padding(.horizontal, 20)
                .padding(.bottom, 8)

            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(group.variants) { vehicle in
                        variantRow(vehicle)
                    }
                }
                .padding(.bottom, 28)
            }
        }
    }

    private func variantRow(_ vehicle: VehicleCatalogItem) -> some View {
        Button {
            pick(vehicle)
        } label: {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(String(vehicle.year))
                    .font(Typography.metric)
                    .foregroundColor(.ink)
                    .frame(width: 64, alignment: .leading)

                VStack(alignment: .leading, spacing: 3) {
                    Text(vehicle.catalogFuelLabel)
                        .font(Typography.readingCardTitle)
                        .foregroundColor(.ink)
                    if let trim = vehicle.trim, !trim.isEmpty {
                        Text(trim)
                            .font(Typography.readingCaption)
                            .foregroundColor(.secondaryText)
                            .lineLimit(1)
                    }
                    Text(vehicle.dimensionsText)
                        .font(Typography.readingCaption)
                        .foregroundColor(.secondaryText)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                if selectedId == vehicle.id {
                    Text("✓")
                        .font(.system(size: 18, weight: .bold, design: .serif))
                        .foregroundStyle(Color.ink)
                }
            }
            .padding(.vertical, 14)
            .padding(.horizontal, 20)
            .overlay(alignment: .bottom) {
                Rectangle()
                    .fill(selectedId == vehicle.id ? Color.accent : Color.hairlineBorder)
                    .frame(height: selectedId == vehicle.id ? 2 : 1)
                    .padding(.horizontal, 20)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(vehicle.displayName), \(vehicle.catalogFuelLabel)")
    }

    // MARK: - Text (grouped by brand)

    private var searchResultsSurface: some View {
        let grouped = searchIndex.searchGrouped(query: query, limit: Self.maxSearchHits)
        return Group {
            if grouped.isEmpty {
                ContentUnavailableView(
                    L10n.vehiclePickerNoResults,
                    systemImage: "car.side",
                    description: Text(L10n.vehiclePickerTryDifferent)
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        ForEach(grouped, id: \.brand) { section in
                            VStack(alignment: .leading, spacing: 0) {
                                Text(section.brand)
                                    .font(Typography.readingCaption.weight(.semibold))
                                    .foregroundColor(.secondaryText)
                                    .padding(.horizontal, 20)
                                    .padding(.bottom, 6)

                                ForEach(section.models) { hit in
                                    let group = ModelGroup(brand: hit.brand, model: hit.model, variants: hit.variants)
                                    Button {
                                        UISelectionFeedbackGenerator().selectionChanged()
                                        searchText = ""
                                        withAnimation(catalogAnimation) {
                                            level = .variants(brand: hit.brand, model: hit.model)
                                        }
                                    } label: {
                                        HStack {
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(group.model)
                                                    .font(Typography.title2)
                                                    .foregroundColor(.ink)
                                                Text("\(group.yearLabel) · \(group.countLabel)")
                                                    .font(Typography.readingCaption)
                                                    .foregroundColor(.secondaryText)
                                            }
                                            Spacer()
                                            Text("→")
                                                .foregroundColor(.secondaryText)
                                        }
                                        .padding(.vertical, 12)
                                        .padding(.horizontal, 20)
                                        .contentShape(Rectangle())
                                    }
                                    .buttonStyle(.plain)

                                    Rectangle()
                                        .fill(Color.hairlineBorder)
                                        .frame(height: 1)
                                        .padding(.horizontal, 20)
                                }
                            }
                        }
                    }
                    .padding(.bottom, 28)
                }
                .scrollDismissesKeyboard(.interactively)
            }
        }
    }

    // MARK: - Helpers

    private func backBar(title: String, action: @escaping () -> Void) -> some View {
        Button {
            withAnimation(catalogAnimation) { action() }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 14, weight: .semibold))
                Text(title)
                    .font(Typography.readingCardTitle)
            }
            .foregroundColor(.ink)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
        }
        .buttonStyle(.plain)
        .accessibilityHint(L10n.vehiclePickerBackA11yHint)
    }

    private func modelGroup(brand: String, model: String) -> ModelGroup? {
        let hits = searchIndex.models(forBrand: brand)
        guard let hit = hits.first(where: { $0.model == model }) else { return nil }
        return ModelGroup(brand: hit.brand, model: hit.model, variants: hit.variants)
    }

    private func pick(_ vehicle: VehicleCatalogItem) {
        selectedId = vehicle.id
        UISelectionFeedbackGenerator().selectionChanged()
        dismiss()
    }
}

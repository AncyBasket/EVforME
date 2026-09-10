//
//  EVforMEWidget.swift
//  EVforMEWidget
//

import AppIntents
import SwiftUI
import WidgetKit

enum WidgetShared {
    static let appGroupID = "group.Gancione.EVforME"
    static let snapshotKey = "evforme.widget.verdictSnapshot"
    static let inputKey = "evforme.widget.mirroredInput"
    static let fuelCustomizedKey = "evforme.autocosts.userCustomizedFuelPrice"
}

struct VerdictWidgetSnapshot: Codable {
    var verdictRaw: String
    var title: String
    var subtitle: String
    var yearlyKm: Int
    var savingsMin: Int
    var savingsMax: Int
    var weeklyCharges: Int
    var fuelPrice: Double
    var iceLPer100Km: Double
    var updatedAt: TimeInterval

    enum CodingKeys: String, CodingKey {
        case verdictRaw, title, subtitle, yearlyKm, savingsMin, savingsMax
        case weeklyCharges, fuelPrice, iceLPer100Km, updatedAt
    }

    init(
        verdictRaw: String,
        title: String,
        subtitle: String,
        yearlyKm: Int,
        savingsMin: Int,
        savingsMax: Int,
        weeklyCharges: Int,
        fuelPrice: Double,
        iceLPer100Km: Double,
        updatedAt: TimeInterval
    ) {
        self.verdictRaw = verdictRaw
        self.title = title
        self.subtitle = subtitle
        self.yearlyKm = yearlyKm
        self.savingsMin = savingsMin
        self.savingsMax = savingsMax
        self.weeklyCharges = weeklyCharges
        self.fuelPrice = fuelPrice
        self.iceLPer100Km = iceLPer100Km
        self.updatedAt = updatedAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        verdictRaw = try c.decode(String.self, forKey: .verdictRaw)
        title = try c.decode(String.self, forKey: .title)
        subtitle = try c.decode(String.self, forKey: .subtitle)
        yearlyKm = try c.decode(Int.self, forKey: .yearlyKm)
        savingsMin = try c.decode(Int.self, forKey: .savingsMin)
        savingsMax = try c.decode(Int.self, forKey: .savingsMax)
        weeklyCharges = try c.decode(Int.self, forKey: .weeklyCharges)
        fuelPrice = try c.decodeIfPresent(Double.self, forKey: .fuelPrice) ?? 1.7
        iceLPer100Km = try c.decodeIfPresent(Double.self, forKey: .iceLPer100Km) ?? 7.0
        updatedAt = try c.decode(TimeInterval.self, forKey: .updatedAt)
    }
}

struct MirroredWidgetInput: Codable {
    var fuelPrice: Double
    var dailyKm: Int
    var iceLPer100Km: Double

    enum CodingKeys: String, CodingKey {
        case fuelPrice, dailyKm, iceLPer100Km
    }

    init(fuelPrice: Double, dailyKm: Int, iceLPer100Km: Double) {
        self.fuelPrice = fuelPrice
        self.dailyKm = dailyKm
        self.iceLPer100Km = iceLPer100Km
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        fuelPrice = try c.decode(Double.self, forKey: .fuelPrice)
        dailyKm = try c.decode(Int.self, forKey: .dailyKm)
        iceLPer100Km = try c.decodeIfPresent(Double.self, forKey: .iceLPer100Km) ?? 7.0
    }
}

enum SnapshotLoader {
    static var suite: UserDefaults {
        UserDefaults(suiteName: WidgetShared.appGroupID) ?? .standard
    }

    static func load() -> VerdictWidgetSnapshot? {
        guard let data = suite.data(forKey: WidgetShared.snapshotKey) else { return nil }
        return try? JSONDecoder().decode(VerdictWidgetSnapshot.self, from: data)
    }

    static func loadMirror() -> MirroredWidgetInput? {
        guard let data = suite.data(forKey: WidgetShared.inputKey) else { return nil }
        return try? JSONDecoder().decode(MirroredWidgetInput.self, from: data)
    }

    static func save(snapshot: VerdictWidgetSnapshot, mirror: MirroredWidgetInput) {
        if let data = try? JSONEncoder().encode(snapshot) {
            suite.set(data, forKey: WidgetShared.snapshotKey)
        }
        if let data = try? JSONEncoder().encode(mirror) {
            suite.set(data, forKey: WidgetShared.inputKey)
        }
        suite.set(true, forKey: WidgetShared.fuelCustomizedKey)
        WidgetCenter.shared.reloadAllTimelines()
    }
}

/// Interactive widget action: raise fuel by €0.10 and refresh the savings band.
struct BumpFuelPriceIntent: AppIntent {
    static var title: LocalizedStringResource = LocalizedStringResource("widget_bump_fuel_title")
    static var description = IntentDescription(LocalizedStringResource("widget_bump_fuel_description"))

    func perform() async throws -> some IntentResult {
        var snap = SnapshotLoader.load()
        let ice = snap?.iceLPer100Km
            ?? SnapshotLoader.loadMirror()?.iceLPer100Km
            ?? 7.0
        var mirror = SnapshotLoader.loadMirror()
            ?? MirroredWidgetInput(
                fuelPrice: snap?.fuelPrice ?? 1.7,
                dailyKm: snap?.yearlyKm ?? 12_000,
                iceLPer100Km: ice
            )

        let bump = 0.10
        mirror.fuelPrice += bump
        mirror.iceLPer100Km = ice
        let litersPerYear = Double(mirror.dailyKm) / 100.0 * ice
        let extra = Int((litersPerYear * bump).rounded())

        if var snap {
            snap.fuelPrice = mirror.fuelPrice
            snap.iceLPer100Km = ice
            snap.savingsMin += extra
            snap.savingsMax += extra
            snap.updatedAt = Date().timeIntervalSince1970
            SnapshotLoader.save(snapshot: snap, mirror: mirror)
        } else {
            let placeholder = VerdictWidgetSnapshot(
                verdictRaw: "maybe",
                title: WidgetL10n.fuelBumpedTitle,
                subtitle: WidgetL10n.fuelPricePerLiter(mirror.fuelPrice),
                yearlyKm: mirror.dailyKm,
                savingsMin: extra,
                savingsMax: extra + 200,
                weeklyCharges: 2,
                fuelPrice: mirror.fuelPrice,
                iceLPer100Km: ice,
                updatedAt: Date().timeIntervalSince1970
            )
            SnapshotLoader.save(snapshot: placeholder, mirror: mirror)
        }
        return .result()
    }
}

struct VerdictEntry: TimelineEntry {
    let date: Date
    let snapshot: VerdictWidgetSnapshot?
}

struct VerdictProvider: TimelineProvider {
    func placeholder(in context: Context) -> VerdictEntry {
        VerdictEntry(
            date: .now,
            snapshot: VerdictWidgetSnapshot(
                verdictRaw: "yes",
                title: WidgetL10n.placeholderTitle,
                subtitle: WidgetL10n.placeholderSubtitle,
                yearlyKm: 12_000,
                savingsMin: 400,
                savingsMax: 900,
                weeklyCharges: 2,
                fuelPrice: 1.7,
                iceLPer100Km: 7.0,
                updatedAt: Date().timeIntervalSince1970
            )
        )
    }

    func getSnapshot(in context: Context, completion: @escaping (VerdictEntry) -> Void) {
        completion(VerdictEntry(date: .now, snapshot: SnapshotLoader.load()))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<VerdictEntry>) -> Void) {
        let entry = VerdictEntry(date: .now, snapshot: SnapshotLoader.load())
        let next = Calendar.current.date(byAdding: .hour, value: 6, to: .now) ?? .now.addingTimeInterval(21_600)
        completion(Timeline(entries: [entry], policy: .after(next)))
    }
}

struct VerdictWidgetView: View {
    var entry: VerdictEntry

    var body: some View {
        Group {
            if let snap = entry.snapshot {
                VStack(alignment: .leading, spacing: 6) {
                    Text(WidgetL10n.brandTitle)
                        .font(.caption.weight(.heavy))
                        .foregroundStyle(.secondary)
                    Text(snap.title)
                        .font(.headline.weight(.black))
                        .lineLimit(2)
                    Text(WidgetL10n.savingsChargesLine(min: snap.savingsMin, max: snap.savingsMax, charges: snap.weeklyCharges))
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Text(WidgetL10n.fuelKmLine(price: snap.fuelPrice, km: snap.yearlyKm))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Button(intent: BumpFuelPriceIntent()) {
                        Text(WidgetL10n.bumpFuelTitle)
                            .font(.caption2.weight(.bold))
                    }
                    .tint(.primary)
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Text(WidgetL10n.brandTitle)
                        .font(.headline.weight(.black))
                    Text(WidgetL10n.emptyPrompt)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .containerBackground(for: .widget) {
            ZStack(alignment: .leading) {
                Color(red: 0.925, green: 0.933, blue: 0.910)
                Rectangle()
                    .fill(Color(red: 0.72, green: 0.92, blue: 0.18))
                    .frame(width: 4)
            }
        }
        .widgetURL(URL(string: "evforme://verdict"))
    }
}

struct EVforMEVerdictWidget: Widget {
    let kind = "EVforMEVerdictWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: VerdictProvider()) { entry in
            VerdictWidgetView(entry: entry)
        }
        .configurationDisplayName(WidgetL10n.configDisplayName)
        .description(WidgetL10n.configDescription)
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct EVforMEWidgetBundle: WidgetBundle {
    var body: some Widget {
        EVforMEVerdictWidget()
        VerdictLiveActivity()
    }
}

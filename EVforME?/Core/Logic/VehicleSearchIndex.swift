//
//  VehicleSearchIndex.swift
//  EVforME?
//
//  Indice ricerca catalogo: nomi comuni, alias IT/EN, marche abbreviate, ranking per modello.
//

import Foundation

/// Ricerca veicoli come la farebbe qualcuno che conosce le auto (non solo substring grezza).
struct VehicleSearchIndex {
    struct Hit: Identifiable {
        let brand: String
        let model: String
        let variants: [VehicleCatalogItem]
        let score: Int

        var id: String { "\(brand)|\(model)".lowercased() }

        var representative: VehicleCatalogItem {
            variants.max(by: { $0.year < $1.year }) ?? variants[0]
        }
    }

    private struct IndexedGroup {
        let brand: String
        let model: String
        let variants: [VehicleCatalogItem]
        let brandNorm: String
        let modelNorm: String
        let modelTokens: [String]
        let allTokens: Set<String>
        let searchBlob: String
        let years: Set<Int>
    }

    private let groups: [IndexedGroup]

    init(vehicles: [VehicleCatalogItem]) {
        let bundled = Dictionary(grouping: vehicles, by: { "\($0.brand)|\($0.model)" })
        groups = bundled.values.compactMap { items -> IndexedGroup? in
            guard let first = items.first else { return nil }
            let sorted = items.sorted { $0.year > $1.year }
            let brandNorm = Self.normalize(first.brand)
            let modelNorm = Self.normalize(first.model)
            let modelTokens = Self.tokenize(first.model)
            var all = Set(modelTokens)
            all.formUnion(Self.tokenize(first.brand))
            if let trim = first.trim {
                all.formUnion(Self.tokenize(trim))
            }
            // Alias espliciti per questa marca/modello.
            for alias in Self.aliases(forBrand: first.brand, model: first.model) {
                all.formUnion(Self.tokenize(alias))
                all.insert(Self.normalize(alias))
            }
            let blob = ([brandNorm, modelNorm] + Array(all)).joined(separator: " ")
            return IndexedGroup(
                brand: first.brand,
                model: first.model,
                variants: sorted,
                brandNorm: brandNorm,
                modelNorm: modelNorm,
                modelTokens: modelTokens,
                allTokens: all,
                searchBlob: blob,
                years: Set(sorted.map(\.year))
            )
        }
    }

    /// Cerca per nome (marca/modello/alias). Query vuota → lista A–Z (limitata dal caller).
    func search(query: String, brandFilter: String? = nil, limit: Int = 80) -> [Hit] {
        var pool = groups
        if let brandFilter {
            let bf = Self.normalize(brandFilter)
            pool = pool.filter { $0.brandNorm == bf || $0.brand == brandFilter }
        }

        let raw = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty else {
            return pool
                .sorted {
                    "\($0.brand) \($0.model)".localizedCaseInsensitiveCompare("\($1.brand) \($1.model)") == .orderedAscending
                }
                .prefix(limit)
                .map { Hit(brand: $0.brand, model: $0.model, variants: $0.variants, score: 0) }
        }

        let expanded = Self.expandQuery(raw)
        let scored: [(IndexedGroup, Int)] = pool.compactMap { group in
            let score = Self.score(group: group, queryTokens: expanded)
            return score > 0 ? (group, score) : nil
        }

        return scored
            .sorted {
                if $0.1 != $1.1 { return $0.1 > $1.1 }
                return "\($0.0.brand) \($0.0.model)".localizedCaseInsensitiveCompare("\($1.0.brand) \($1.0.model)") == .orderedAscending
            }
            .prefix(limit)
            .map { Hit(brand: $0.0.brand, model: $0.0.model, variants: $0.0.variants, score: $0.1) }
    }

    // MARK: - Scoring

    private static func score(group: IndexedGroup, queryTokens: [String]) -> Int {
        guard !queryTokens.isEmpty else { return 0 }

        var score = 0
        var matchedAll = true

        for token in queryTokens {
            if let year = Int(token), (1990...2035).contains(year) {
                if group.years.contains(year) {
                    score += 80
                } else {
                    // Anno non presente: non escludere del tutto se altri token matchano.
                    matchedAll = false
                }
                continue
            }

            let brandHit = matchBrand(token, brandNorm: group.brandNorm)
            let modelHit = matchModel(token, group: group)
            let blobHit = group.searchBlob.contains(token) || group.allTokens.contains(token)

            if brandHit > 0 {
                score += brandHit
            } else if modelHit > 0 {
                score += modelHit
            } else if blobHit {
                score += 40
            } else {
                matchedAll = false
            }
        }

        guard matchedAll || score >= 120 else { return 0 }
        if !matchedAll { score /= 2 }

        // Bonus: query intera ≈ nome modello.
        let joined = queryTokens.joined(separator: " ")
        if group.modelNorm == joined { score += 500 }
        else if group.modelNorm.hasPrefix(joined) { score += 220 }
        if group.brandNorm == joined { score += 180 }

        return score
    }

    private static func matchBrand(_ token: String, brandNorm: String) -> Int {
        if brandNorm == token { return 320 }
        if brandNorm.hasPrefix(token), token.count >= 2 { return 200 }
        if brandAliases[token] == brandNorm { return 300 }
        if token.count >= 3, brandNorm.contains(token) { return 90 }
        return 0
    }

    private static func matchModel(_ token: String, group: IndexedGroup) -> Int {
        if group.modelNorm == token { return 900 }
        // Token esatto tra pezzi del modello ("golf" in "Golf GTI", "3" in "3 Series").
        if group.modelTokens.contains(token) {
            // Evita che "5" prenda troppo peso da solo su "5008" ecc. se è solo una cifra
            // e non è un token modello significativo: le serie BMW/MB usano 1 cifra.
            if token.count == 1, Int(token) != nil {
                return 260
            }
            return 700
        }
        if group.modelNorm.hasPrefix(token), token.count >= 2 { return 520 }
        // Prefisso su un token modello ("500" → "500e", "500x") ma non "500" → "5008" come equal weight.
        for mt in group.modelTokens {
            if mt == token { return 700 }
            if mt.hasPrefix(token), token.count >= 2 {
                let rest = mt.dropFirst(token.count)
                // "500"+"e" ok; "500"+"8" (diventa un altro modello numerico) meno forte.
                if rest.first?.isNumber == true, token.contains(where: \.isNumber) {
                    return 180
                }
                return 480
            }
        }
        if token.count >= 3, group.modelNorm.contains(token) { return 120 }
        return 0
    }

    // MARK: - Query expansion

    /// Espande query utente con alias (es. "serie 3" → anche "3 series").
    private static func expandQuery(_ raw: String) -> [String] {
        let norm = normalize(raw)
        var baseTokens = tokenize(raw)

        // Frasi multi-token note.
        for (phrase, expansions) in phraseAliases {
            if norm == phrase || norm.contains(phrase) {
                for exp in expansions {
                    baseTokens.append(contentsOf: tokenize(exp))
                }
            }
        }

        // Alias singola parola.
        var expanded: [String] = []
        for t in baseTokens {
            expanded.append(t)
            if let brand = brandAliases[t] {
                expanded.append(contentsOf: tokenize(brand))
            }
            if let alts = tokenAliases[t] {
                expanded.append(contentsOf: alts.flatMap { tokenize($0) })
            }
        }

        // Dedup preservando ordine.
        var seen = Set<String>()
        return expanded.filter { seen.insert($0).inserted && !$0.isEmpty }
    }

    // MARK: - Normalization

    static func normalize(_ string: String) -> String {
        let folded = string
            .folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "it_IT"))
            .lowercased()
        let scalars = folded.unicodeScalars.map { scalar -> Character in
            if CharacterSet.alphanumerics.contains(scalar) { return Character(scalar) }
            return " "
        }
        return String(scalars)
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
    }

    static func tokenize(_ string: String) -> [String] {
        let norm = normalize(string)
        var out: [String] = []
        for piece in norm.split(separator: " ").map(String.init) {
            out.append(piece)
            // Spezza alfanumerici: "500e" → "500","e","500e"; "id3" → "id","3","id3"
            let parts = splitAlphaNumeric(piece)
            if parts.count > 1 {
                out.append(contentsOf: parts)
            }
        }
        return out.filter { !$0.isEmpty }
    }

    private static func splitAlphaNumeric(_ s: String) -> [String] {
        var parts: [String] = []
        var current = ""
        var lastWasDigit: Bool?
        for ch in s {
            let isDigit = ch.isNumber
            if let lastWasDigit, lastWasDigit != isDigit, !current.isEmpty {
                parts.append(current)
                current = ""
            }
            current.append(ch)
            lastWasDigit = isDigit
        }
        if !current.isEmpty { parts.append(current) }
        return parts
    }

    // MARK: - Alias tables (IT + common shorthand)

    /// Marche come le scrive la gente.
    private static let brandAliases: [String: String] = [
        "vw": "volkswagen",
        "volks": "volkswagen",
        "volkswagen": "volkswagen",
        "merce": "mercedes benz",
        "mercedes": "mercedes benz",
        "benz": "mercedes benz",
        "mb": "mercedes benz",
        "merc": "mercedes benz",
        "alfa": "alfa romeo",
        "alfaromeo": "alfa romeo",
        "citroen": "citroen",
        "citroën": "citroen",
        "ds": "ds",
        "gm": "chevrolet",
        "chevy": "chevrolet",
        "landrover": "land rover",
        "range": "land rover",
        "rr": "land rover",
        "mini": "mini",
        "bmw": "bmw",
        "audi": "audi",
        "fiat": "fiat",
        "toyota": "toyota",
        "tesla": "tesla",
        "renault": "renault",
        "peugeot": "peugeot",
        "opel": "opel",
        "ford": "ford",
        "hyundai": "hyundai",
        "kia": "kia",
        "nissan": "nissan",
        "volvo": "volvo",
        "skoda": "skoda",
        "škoda": "skoda",
        "seat": "seat",
        "cupra": "cupra",
        "jeep": "jeep",
        "dacia": "dacia",
        "suzuki": "suzuki",
        "mazda": "mazda",
        "honda": "honda",
        "lexus": "lexus",
        "porsche": "porsche",
        "ferrari": "ferrari",
        "lamborghini": "lamborghini",
        "lambo": "lamborghini",
        "maserati": "maserati",
        "byd": "byd",
        "mg": "mg",
        "smart": "smart",
    ]

    /// Token → alternative di modello.
    private static let tokenAliases: [String: [String]] = [
        "serie": ["series"],
        "series": ["serie", "series"],
        "classe": ["class"],
        "class": ["classe", "class"],
        "modello": ["model"],
        "model": ["modello", "model"],
        "panda": ["panda"],
        "punto": ["punto"],
        "tipo": ["tipo"],
        "giulia": ["giulia"],
        "stelvio": ["stelvio"],
        "tonale": ["tonale"],
        "500e": ["500e", "500 e"],
        "500x": ["500x", "500 x"],
        "500l": ["500l", "500 l"],
        "id3": ["id 3", "id.3", "id3"],
        "id4": ["id 4", "id.4", "id4"],
        "id5": ["id 5", "id.5", "id5"],
        "id7": ["id 7", "id.7", "id7"],
        "idbuzz": ["id buzz", "buzz"],
        "egolf": ["e golf", "golf"],
        "leaf": ["leaf"],
        "zoe": ["zoe", "zoé"],
        "twingo": ["twingo"],
        "clio": ["clio"],
        "megane": ["megane", "mégane"],
        "captur": ["captur"],
        "scenic": ["scenic", "scénic"],
        "ioniq": ["ioniq"],
        "kona": ["kona"],
        "tucson": ["tucson"],
        "sportage": ["sportage"],
        "niro": ["niro"],
        "ev6": ["ev6", "ev 6"],
        "ev9": ["ev9", "ev 9"],
        "qashqai": ["qashqai"],
        "juke": ["juke"],
        "ariya": ["ariya"],
        "corsa": ["corsa"],
        "astra": ["astra"],
        "mokka": ["mokka"],
        "polo": ["polo"],
        "golf": ["golf"],
        "tiguan": ["tiguan"],
        "passat": ["passat"],
        "troc": ["t roc", "t-roc", "troc"],
        "tayron": ["tayron"],
        "octavia": ["octavia"],
        "fabia": ["fabia"],
        "enyaq": ["enyaq"],
        "leon": ["leon", "león"],
        "ibiza": ["ibiza"],
        "born": ["born"],
        "formentor": ["formentor"],
        "yaris": ["yaris"],
        "corolla": ["corolla"],
        "rav4": ["rav4", "rav 4"],
        "chr": ["c hr", "c-hr", "chr"],
        "aygo": ["aygo"],
        "bZ4X": ["bz4x", "b z 4 x"],
        "bz4x": ["bz4x"],
        "fiesta": ["fiesta"],
        "focus": ["focus"],
        "puma": ["puma"],
        "kuga": ["kuga"],
        "mustang": ["mustang"],
        "mach": ["mach e", "mache"],
        "mache": ["mach e", "mustang"],
        "208": ["208"],
        "2008": ["2008"],
        "3008": ["3008"],
        "308": ["308"],
        "e208": ["e 208", "208"],
        "i3": ["i3", "i 3"],
        "i4": ["i4", "i 4"],
        "i5": ["i5", "i 5"],
        "i7": ["i7", "i 7"],
        "ix": ["ix", "i x"],
        "x1": ["x1", "x 1"],
        "x3": ["x3", "x 3"],
        "x5": ["x5", "x 5"],
        "q3": ["q3", "q 3"],
        "q4": ["q4", "q 4"],
        "q5": ["q5", "q 5"],
        "q8": ["q8", "q 8"],
        "etron": ["e tron", "e-tron", "etron"],
        "a3": ["a3", "a 3"],
        "a4": ["a4", "a 4"],
        "a6": ["a6", "a 6"],
        "cybertruck": ["cybertruck", "cyber"],
        "sandero": ["sandero"],
        "duster": ["duster"],
        "spring": ["spring"],
        "renegade": ["renegade"],
        "compass": ["compass"],
        "avenger": ["avenger"],
        "ypsilon": ["ypsilon", "lancia y"],
        "delta": ["delta"],
    ]

    /// Frasi intere tipiche IT/EN.
    private static let phraseAliases: [String: [String]] = [
        "serie 1": ["1 series", "bmw 1"],
        "serie 2": ["2 series", "bmw 2"],
        "serie 3": ["3 series", "bmw 3"],
        "serie 4": ["4 series", "bmw 4"],
        "serie 5": ["5 series", "bmw 5"],
        "serie 7": ["7 series", "bmw 7"],
        "1 series": ["serie 1"],
        "2 series": ["serie 2"],
        "3 series": ["serie 3"],
        "4 series": ["serie 4"],
        "5 series": ["serie 5"],
        "classe a": ["a class", "a-class"],
        "classe b": ["b class", "b-class"],
        "classe c": ["c class", "c-class"],
        "classe e": ["e class", "e-class"],
        "classe s": ["s class", "s-class"],
        "classe g": ["g class", "g-class"],
        "a class": ["classe a", "a-class"],
        "c class": ["classe c", "c-class"],
        "e class": ["classe e", "e-class"],
        "model 3": ["modello 3", "tesla 3"],
        "model y": ["modello y", "tesla y"],
        "model s": ["modello s", "tesla s"],
        "model x": ["modello x", "tesla x"],
        "modello 3": ["model 3"],
        "modello y": ["model y"],
        "id 3": ["id3", "id.3"],
        "id 4": ["id4", "id.4"],
        "id 5": ["id5", "id.5"],
        "id 7": ["id7", "id.7"],
        "id buzz": ["id.buzz", "buzz"],
        "e golf": ["e-golf", "egolf"],
        "t roc": ["t-roc", "troc"],
        "c hr": ["c-hr", "chr"],
        "mach e": ["mach-e", "mustang mach"],
        "fiat 500": ["500", "500e"],
        "500 elettrica": ["500e"],
        "panda": ["fiat panda"],
        "golf gti": ["golf gti"],
        "ioniq 5": ["ioniq5"],
        "ioniq 6": ["ioniq6"],
        "q4 etron": ["q4 e-tron", "q4"],
        "e tron": ["e-tron", "etron"],
    ]

    private static func aliases(forBrand brand: String, model: String) -> [String] {
        let b = normalize(brand)
        let m = normalize(model)
        var extras: [String] = []

        // BMW "3 Series" ↔ "serie 3"
        if b == "bmw", m.contains("series") {
            let num = m.split(separator: " ").first.map(String.init) ?? ""
            if !num.isEmpty {
                extras.append("serie \(num)")
                extras.append("bmw \(num)")
            }
        }
        // Mercedes "C-Class" ↔ "classe c"
        if b.contains("mercedes"), m.contains("class") {
            let letter = m.split(whereSeparator: { !$0.isLetter }).first.map(String.init)?.lowercased() ?? ""
            if letter.count == 1 {
                extras.append("classe \(letter)")
            }
        }
        // Tesla Model *
        if b == "tesla", m.hasPrefix("model") {
            let rest = m.replacingOccurrences(of: "model", with: "").trimmingCharacters(in: .whitespaces)
            extras.append("modello \(rest)")
            extras.append("tesla \(rest)")
        }
        // VW ID.*
        if b == "volkswagen", m.hasPrefix("id") {
            extras.append(m.replacingOccurrences(of: " ", with: ""))
            extras.append(m.replacingOccurrences(of: ".", with: " "))
        }
        return extras
    }
}

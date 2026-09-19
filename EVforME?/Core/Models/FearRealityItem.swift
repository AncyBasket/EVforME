//
//  FearRealityItem.swift
//  EVforME?
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import Foundation

struct FearRealityItem: Identifiable, Equatable {
    let id: UUID
    let fear: String
    let reality: String

    init(fear: String, reality: String) {
        self.id = UUID()
        self.fear = fear
        self.reality = reality
    }
}

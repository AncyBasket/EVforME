//
//  CatalogSignposts.swift
//  EVforME?
//
//  os_signpost markers for Instruments (App Launch / Points of Interest).
//

import Foundation
import os.signpost

enum CatalogSignposts {
    private static let log = OSLog(subsystem: "Gancione.EVforME-", category: "Catalog")

    enum load {
        static func begin() {
            os_signpost(.begin, log: CatalogSignposts.log, name: "CatalogLoad")
        }

        static func end() {
            os_signpost(.end, log: CatalogSignposts.log, name: "CatalogLoad")
        }
    }
}

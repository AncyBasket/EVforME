//
//  StickerOCRService.swift
//  EVforME?
//
//  OCR on-device (Vision) per libretto / sticker consumi.
//

import Foundation
import UIKit
import Vision

struct StickerOCRResult {
    let rawText: String
    let fuelLPer100Km: Double?
    let energyKWhPer100Km: Double?
}

enum StickerOCRService {
    static func recognize(from image: UIImage) async -> StickerOCRResult {
        guard let cgImage = image.cgImage else {
            return StickerOCRResult(rawText: "", fuelLPer100Km: nil, energyKWhPer100Km: nil)
        }

        return await withCheckedContinuation { continuation in
            let request = VNRecognizeTextRequest { request, _ in
                let observations = (request.results as? [VNRecognizedTextObservation]) ?? []
                let lines = observations.compactMap { $0.topCandidates(1).first?.string }
                let joined = lines.joined(separator: "\n")
                continuation.resume(returning: parse(joined))
            }
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            request.recognitionLanguages = ["it-IT", "en-US"]

            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    try handler.perform([request])
                } catch {
                    continuation.resume(returning: StickerOCRResult(rawText: "", fuelLPer100Km: nil, energyKWhPer100Km: nil))
                }
            }
        }
    }

    private static func parse(_ text: String) -> StickerOCRResult {
        let normalized = text
            .replacingOccurrences(of: ",", with: ".")
            .lowercased()

        let fuel = firstMatch(in: normalized, patterns: [
            #"(\d+(?:\.\d+)?)\s*l\s*/\s*100"#,
            #"(\d+(?:\.\d+)?)\s*l/100"#,
            #"consumo[^\d]{0,12}(\d+(?:\.\d+)?)"#
        ])
        let energy = firstMatch(in: normalized, patterns: [
            #"(\d+(?:\.\d+)?)\s*kwh\s*/\s*100"#,
            #"(\d+(?:\.\d+)?)\s*kwh/100"#
        ])

        return StickerOCRResult(
            rawText: text,
            fuelLPer100Km: fuel.flatMap { v in (3...20).contains(v) ? v : nil },
            energyKWhPer100Km: energy.flatMap { v in (8...40).contains(v) ? v : nil }
        )
    }

    private static func firstMatch(in text: String, patterns: [String]) -> Double? {
        for pattern in patterns {
            guard let regex = try? NSRegularExpression(pattern: pattern) else { continue }
            let range = NSRange(text.startIndex..<text.endIndex, in: text)
            guard let match = regex.firstMatch(in: text, range: range),
                  match.numberOfRanges > 1,
                  let r = Range(match.range(at: 1), in: text) else { continue }
            if let value = Double(text[r]) { return value }
        }
        return nil
    }
}

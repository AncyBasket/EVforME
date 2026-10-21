import XCTest
@testable import EVforME_

final class VerdictExplanationServiceTests: XCTestCase {
    private func sampleResult() -> SimulationResult {
        SimulationResult(
            verdict: .yes,
            weeklyCharges: 2,
            yearlySavingsRange: 400...600,
            breakEvenMonths: nil,
            keyReasons: ["Casa"],
            fearReality: [],
            yearlyComparison: [],
            sourceYearlyBreakdown: OperatingCostBreakdown(
                energy: 1000, maintenance: 400, taxes: 200, insurance: 400, taxesKnown: true
            ),
            targetYearlyBreakdown: OperatingCostBreakdown(
                energy: 600, maintenance: 300, taxes: 0, insurance: 500, taxesKnown: true
            )
        )
    }

    private func sampleInput() -> UserInput {
        UserInput(
            dailyKm: 12_000,
            hasHomeCharging: true,
            areaType: .mixed,
            fuelPrice: 1.80,
            ownershipYears: 5
        )
    }

    func testAIExplanation_RejectsAnyDigits_AcceptsQualitative() {
        let result = sampleResult()
        let input = sampleInput()

        XCTAssertTrue(
            VerdictExplanationService.containsDisallowedFigures(
                "Risparmi circa 999 euro l'anno.",
                relativeTo: result,
                input: input
            )
        )
        XCTAssertTrue(
            VerdictExplanationService.containsDisallowedFigures(
                "Fai 12000 km all'anno.",
                relativeTo: result,
                input: input
            )
        )
        XCTAssertFalse(
            VerdictExplanationService.containsDisallowedFigures(
                "Con ricarica a casa e tanti km il sì è coerente.",
                relativeTo: result,
                input: input
            )
        )
    }
}

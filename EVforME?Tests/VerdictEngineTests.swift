//
//  VerdictEngineTests.swift
//  EVforME?Tests
//
//  Created by Andrea Ancellotti on 29/01/26.
//

import XCTest
@testable import EVforME_

final class VerdictEngineTests: XCTestCase {

    private func emptyBreakdown(total: Double) -> OperatingCostBreakdown {
        OperatingCostBreakdown(energy: total, maintenance: 0, taxes: 0, insurance: 0)
    }

    private func makeResult(
        iceTotal: Double,
        evTotal: Double,
        yearlyIce: Double,
        yearlyEv: Double
    ) -> EVSimulationResult {
        EVSimulationResult(
            iceTotalCost: iceTotal,
            evTotalCost: evTotal,
            totalSavings: iceTotal - evTotal,
            yearlyIceCost: yearlyIce,
            yearlyEvCost: yearlyEv,
            sourceBreakdown: emptyBreakdown(total: yearlyIce),
            targetBreakdown: emptyBreakdown(total: yearlyEv)
        )
    }

    func testVerdictIsNotAlwaysYes() {
        let badResult = makeResult(iceTotal: 5000, evTotal: 6000, yearlyIce: 1000, yearlyEv: 1200)

        let verdict = VerdictEngine.evaluate(
            result: badResult,
            scenario: .realistic
        )

        XCTAssertEqual(verdict, .notYet)
    }

    func testOptimisticScenarioIsMorePermissive() {
        let okResult = makeResult(iceTotal: 9000, evTotal: 5000, yearlyIce: 1800, yearlyEv: 1100)

        let verdictOptimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .optimistic
        )

        let verdictPessimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .pessimistic
        )

        XCTAssertNotEqual(verdictOptimistic, verdictPessimistic)
    }

    func testYesRequiresPaybackWithinOwnershipHorizon() {
        // Strong opex savings, but huge premium → no payback in 5 years.
        let strongOpex = makeResult(
            iceTotal: 40_000,
            evTotal: 20_000,
            yearlyIce: 8_000,
            yearlyEv: 4_000
        )
        // Yearly delta 4000 → premium 80_000 needs 20 years.
        let blocked = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .optimistic,
            netPurchasePremiumEUR: 80_000,
            ownershipYears: 5
        )
        XCTAssertEqual(blocked, .maybe)

        let unlocked = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .optimistic,
            netPurchasePremiumEUR: 5_000,
            ownershipYears: 5
        )
        XCTAssertEqual(unlocked, .yes)
    }
}

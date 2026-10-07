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
        // Mid-band savings: clears optimistic purchase thresholds, not pessimistic.
        let okResult = makeResult(iceTotal: 9000, evTotal: 5000, yearlyIce: 1800, yearlyEv: 1100)

        let verdictOptimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .optimistic,
            netPurchasePremiumEUR: 2_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )

        let verdictPessimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .pessimistic,
            netPurchasePremiumEUR: 2_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
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

    func testOpexOnly_IgnoresHugeListPricePremium() {
        // Same strong opex as above; purchase mode blocks, owned mode can say yes.
        let strongOpex = makeResult(
            iceTotal: 40_000,
            evTotal: 20_000,
            yearlyIce: 8_000,
            yearlyEv: 4_000
        )
        let purchase = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .realistic,
            netPurchasePremiumEUR: 80_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )
        XCTAssertNotEqual(purchase, .yes)

        let owned = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .realistic,
            netPurchasePremiumEUR: 0,
            ownershipYears: 5,
            comparisonIntent: .alreadyOwned
        )
        XCTAssertEqual(owned, .yes)
    }

    func testOpexOnly_ZeroYearlyDelta_IsNotYet() {
        let flat = makeResult(iceTotal: 10_000, evTotal: 10_000, yearlyIce: 2_000, yearlyEv: 2_000)
        let verdict = VerdictEngine.evaluate(
            result: flat,
            scenario: .realistic,
            netPurchasePremiumEUR: 0,
            ownershipYears: 5,
            comparisonIntent: .alreadyOwned
        )
        XCTAssertEqual(verdict, .notYet)
    }
}

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
        // Mid-band opex: clears optimistic thresholds, not pessimistic.
        // optimistic: savings>1500, delta>250; pessimistic: savings>2500, delta>450
        let okResult = makeResult(iceTotal: 10_000, evTotal: 8_000, yearlyIce: 2_000, yearlyEv: 1_700)

        let verdictOptimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .optimistic,
            netPurchasePremiumEUR: 80_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )

        let verdictPessimistic = VerdictEngine.evaluate(
            result: okResult,
            scenario: .pessimistic,
            netPurchasePremiumEUR: 80_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )

        XCTAssertEqual(verdictOptimistic, .yes)
        XCTAssertEqual(verdictPessimistic, .maybe)
        XCTAssertNotEqual(verdictOptimistic, verdictPessimistic)
    }

    func testListPricePremiumDoesNotBlockStrongOpex() {
        // Strong opex savings: listino alto non deve più bloccare il sì.
        let strongOpex = makeResult(
            iceTotal: 40_000,
            evTotal: 20_000,
            yearlyIce: 8_000,
            yearlyEv: 4_000
        )
        let withHugePremium = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .optimistic,
            netPurchasePremiumEUR: 80_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )
        XCTAssertEqual(withHugePremium, .yes)

        let withSmallPremium = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .optimistic,
            netPurchasePremiumEUR: 5_000,
            ownershipYears: 5,
            comparisonIntent: .consideringPurchase
        )
        XCTAssertEqual(withSmallPremium, .yes)
    }

    func testPurchaseAndOwned_SameVerdictWhenOpexStrong() {
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
        let owned = VerdictEngine.evaluate(
            result: strongOpex,
            scenario: .realistic,
            netPurchasePremiumEUR: 0,
            ownershipYears: 5,
            comparisonIntent: .alreadyOwned
        )
        XCTAssertEqual(purchase, .yes)
        XCTAssertEqual(owned, .yes)
        XCTAssertEqual(purchase, owned)
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

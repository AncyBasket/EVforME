# Come calcoliamo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Trust screen for both cars’ number sources + prominent chargers entry on verdict; single source of truth for displayed constants.

**Architecture:** Pure `HowWeCalculateExplainer` + SwiftUI view; CO₂ factors in `FuelFromCO2Constants`; bollo via existing `ItalianRegion` / `EVSimulator` APIs.

**Tech stack:** SwiftUI, XCTest, existing smoke UITest patterns.

## Tasks

1. Add `FuelFromCO2Constants` (petrol/diesel factors + EUR-Lex URL) matching Python script; unit test equality.
2. Add `HowWeCalculateExplainer` + confidence bands; tests for Molise/Lazio/Lombardia tariff parity.
3. Add `HowWeCalculateView` + L10n IT/EN; wire VerdictView + GuidesHubView.
4. ChargingMapView: `preferDeviceLocation`; denied → Settings CTA; VerdictView prominent button.
5. Privacy / Info.plist location strings if needed.
6. Smoke shots + unit/UI green; draft PR (no version/CDN).

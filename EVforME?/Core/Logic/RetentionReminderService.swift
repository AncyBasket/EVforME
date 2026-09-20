//
//  RetentionReminderService.swift
//  EVforME?
//
//  Reminder locali soft (30 / 90 giorni) dopo il primo verdetto — zero spam.
//  Al fire/tap: se i dati non si sono mossi → apri ultimo confronto; se sì → ricalcolo live.
//

import Foundation
import UserNotifications

final class RetentionReminderService: NSObject {
    static let shared = RetentionReminderService()

    private enum IDs {
        static let day30 = "evforme.retention.30d"
        static let day90 = "evforme.retention.90d"
    }

    private enum Keys {
        static let permissionAsked = "evforme.retention.permissionAsked"
        static let armed = "evforme.retention.armed"
    }

    private let defaults = UserDefaults.standard
    private let center = UNUserNotificationCenter.current()

    private override init() {
        super.init()
        center.delegate = self
    }

    /// Chiamato dopo il salvataggio di uno scenario. Chiede permesso una sola volta.
    func armAfterVerdictSaved() {
        defaults.set(true, forKey: Keys.armed)
        Task { @MainActor in
            await requestPermissionIfNeeded()
            await scheduleRemindersIfAuthorized()
        }
    }

    /// Su launch/foreground: assicurati che i reminder esistano se già armati.
    func reconcileOnForeground() {
        guard defaults.bool(forKey: Keys.armed) else { return }
        Task { @MainActor in
            await scheduleRemindersIfAuthorized()
        }
    }

    @MainActor
    private func requestPermissionIfNeeded() async {
        if defaults.bool(forKey: Keys.permissionAsked) { return }
        defaults.set(true, forKey: Keys.permissionAsked)
        _ = try? await center.requestAuthorization(options: [.alert, .sound])
    }

    @MainActor
    private func scheduleRemindersIfAuthorized() async {
        guard ScenarioHistoryStore.latest() != nil else {
            center.removePendingNotificationRequests(withIdentifiers: [IDs.day30, IDs.day90])
            return
        }

        let settings = await center.notificationSettings()
        guard settings.authorizationStatus == .authorized
                || settings.authorizationStatus == .provisional
                || settings.authorizationStatus == .ephemeral else {
            return
        }

        let pending = await center.pendingNotificationRequests()
        let ids = Set(pending.map(\.identifier))
        if !ids.contains(IDs.day30) {
            schedule(id: IDs.day30, days: 30)
        }
        if !ids.contains(IDs.day90) {
            schedule(id: IDs.day90, days: 90)
        }
    }

    private func schedule(id: String, days: Int) {
        let content = UNMutableNotificationContent()
        content.title = L10n.retentionNotifTitle
        content.body = L10n.retentionNotifBody
        content.sound = .default
        content.userInfo = [
            "deepLink": AppDeepLink.recalculateURL.absoluteString
        ]

        let fire = Date().addingTimeInterval(TimeInterval(days * 24 * 60 * 60))
        let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: fire)
        let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
        let request = UNNotificationRequest(identifier: id, content: content, trigger: trigger)
        center.add(request) { error in
            if let error {
                AppLogger.shared.warning(
                    "Failed to schedule retention reminder \(id): \(error.localizedDescription)",
                    category: .analytics
                )
            }
        }
    }

    private func routeFromNotification() {
        guard let snap = ScenarioHistoryStore.latest() else {
            AppDeepLink.requestOpenLastVerdict()
            return
        }
        // Al fire: ricalcolo solo se i dati live sono mossi oltre soglia; altrimenti apri ultimo.
        if ScenarioLiveDelta.liveDataMoved(versus: snap) {
            AppDeepLink.requestRecalculateLastComparison()
        } else {
            AppDeepLink.requestOpenLastVerdict()
        }
    }
}

extension RetentionReminderService: UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        // In foreground: mostra solo se i dati sono cambiati (evita spam se invariati).
        if let snap = ScenarioHistoryStore.latest(), ScenarioLiveDelta.liveDataMoved(versus: snap) {
            completionHandler([.banner, .sound])
        } else {
            completionHandler([])
        }
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        routeFromNotification()
        completionHandler()
    }
}

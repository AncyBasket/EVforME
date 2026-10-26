//
//  ErrorHandlingViewModifier.swift
//  EVforME?
//
//  View modifier for automatic error handling in SwiftUI views
//

import SwiftUI

struct ErrorHandlingViewModifier: ViewModifier {
    @State private var currentError: AppError?
    @State private var currentUserMessage: String?
    @State private var currentContext: ErrorContext = .general
    @State private var showErrorAlert = false

    func body(content: Content) -> some View {
        content
            .onReceive(NotificationCenter.default.publisher(for: .errorOccurred)) { notification in
                if let notification = notification.userInfo?["notification"] as? ErrorNotification {
                    handleNotification(notification)
                }
            }
            .alert(isPresented: $showErrorAlert) {
                makeErrorAlert()
            }
    }

    private func handleNotification(_ notification: ErrorNotification) {
        currentError = notification.error
        currentUserMessage = notification.userMessage
        currentContext = notification.context
        showErrorAlert = true

        #if DEBUG
        print("Error in \(notification.context.rawValue): \(notification.error.localizedDescription)")
        #endif
    }

    private var isCatalogPickPrompt: Bool {
        guard currentContext == .catalog else { return false }
        if currentUserMessage == L10n.catalogVehiclePickAnother { return true }
        if currentUserMessage == L10n.catalogVehiclePickVersion { return true }
        if currentError == .dataNotFound { return true }
        if case .vehicleNotFound = currentError { return true }
        return false
    }

    private func makeErrorAlert() -> Alert {
        let message = currentUserMessage
            ?? errorMessage(for: currentError)
            ?? L10n.errorUnknown

        if isCatalogPickPrompt {
            return Alert(
                title: Text(L10n.errorTitleCatalog),
                message: Text(message),
                primaryButton: .default(Text(L10n.catalogVehicleChooseAction)) {
                    showErrorAlert = false
                    NotificationCenter.default.post(name: .catalogVehicleSelectionRequested, object: nil)
                },
                secondaryButton: .cancel(Text(L10n.dismiss)) {
                    showErrorAlert = false
                }
            )
        }

        guard let error = currentError else {
            return Alert(
                title: Text(L10n.errorTitleGeneral),
                message: Text(message),
                dismissButton: .cancel(Text(L10n.dismiss)) {
                    showErrorAlert = false
                }
            )
        }
        if error.isRecoverable {
            return Alert(
                title: Text(errorTitle(for: error)),
                message: Text(message),
                primaryButton: .default(Text(L10n.retry)) {
                    showErrorAlert = false
                },
                secondaryButton: .cancel(Text(L10n.dismiss)) {
                    showErrorAlert = false
                }
            )
        }
        return Alert(
            title: Text(errorTitle(for: error)),
            message: Text(message),
            dismissButton: .cancel(Text(L10n.dismiss)) {
                showErrorAlert = false
            }
        )
    }

    private func errorTitle(for error: AppError) -> String {
        switch error {
        case .networkUnavailable, .networkTimeout:
            return L10n.errorTitleNetwork
        case .dataCorrupted, .storageCorrupted:
            return L10n.errorTitleData
        case .catalogLoadFailed, .catalogParseFailed, .dataNotFound, .vehicleNotFound:
            return L10n.errorTitleCatalog
        case .validationFailed, .invalidInput:
            return L10n.errorTitleValidation
        default:
            return L10n.errorTitleGeneral
        }
    }

    private func errorMessage(for error: AppError?) -> String? {
        guard let error else { return nil }
        var message = error.errorDescription ?? L10n.errorUnknown
        if let suggestion = error.recoverySuggestion {
            message += "\n\n\(suggestion)"
        }
        return message
    }
}

extension View {
    /// Apply automatic error handling to a view
    func withErrorHandling() -> some View {
        self.modifier(ErrorHandlingViewModifier())
    }
}

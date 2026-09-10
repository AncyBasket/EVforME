//
//  ErrorHandlingViewModifier.swift
//  EVforME?
//
//  View modifier for automatic error handling in SwiftUI views
//

import SwiftUI

struct ErrorHandlingViewModifier: ViewModifier {
    @State private var currentError: AppError?
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
        showErrorAlert = true
        
        // Log per debugging
        #if DEBUG
        print("Error in \(notification.context.rawValue): \(notification.error.localizedDescription)")
        #endif
    }
    
    private func makeErrorAlert() -> Alert {
        guard let error = currentError else {
            return Alert(
                title: Text(L10n.errorTitleGeneral),
                message: Text(L10n.errorUnknown),
                dismissButton: .cancel(Text(L10n.dismiss)) {
                    showErrorAlert = false
                }
            )
        }
        if error.isRecoverable {
            return Alert(
                title: Text(errorTitle(for: error)),
                message: Text(errorMessage(for: error)),
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
            message: Text(errorMessage(for: error)),
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
        case .catalogLoadFailed, .catalogParseFailed:
            return L10n.errorTitleCatalog
        case .validationFailed, .invalidInput:
            return L10n.errorTitleValidation
        default:
            return L10n.errorTitleGeneral
        }
    }
    
    private func errorMessage(for error: AppError) -> String {
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

// MARK: - Usage Example

/*
 In any SwiftUI view, simply add the modifier:
 
 struct MyView: View {
     var body: some View {
         VStack {
             // Your content
         }
         .withErrorHandling()
     }
 }
 
 Errors posted via ErrorHandler.shared will automatically show alerts.
 */
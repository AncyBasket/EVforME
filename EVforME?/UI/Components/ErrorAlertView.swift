//
//  ErrorAlertView.swift
//  EVforME?
//
//  Reusable error alert component
//

import SwiftUI

struct ErrorAlertView: View {
    let error: AppError
    let onDismiss: () -> Void
    let onRetry: (() -> Void)?
    
    init(error: AppError, onDismiss: @escaping () -> Void, onRetry: (() -> Void)? = nil) {
        self.error = error
        self.onDismiss = onDismiss
        self.onRetry = onRetry
    }
    
    var body: some View {
        VStack(spacing: 20) {
            // Error icon
            Image(systemName: errorIcon)
                .font(.system(size: 40))
                .foregroundColor(errorColor)
            
            // Error title
            Text(errorTitle)
                .font(Typography.title2)
                .foregroundColor(.ink)
                .multilineTextAlignment(.center)
            
            // Error description
            Text(error.errorDescription ?? L10n.errorUnknown)
                .font(Typography.readingBody)
                .foregroundColor(.secondaryText)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            
            // Recovery suggestion
            if let suggestion = error.recoverySuggestion {
                Text(suggestion)
                    .font(Typography.readingCaption)
                    .foregroundColor(.secondaryText)
                    .multilineTextAlignment(.center)
                    .padding(.top, 8)
            }
            
            // Buttons
            VStack(spacing: 12) {
                if let onRetry = onRetry, error.isRecoverable {
                    Button(action: onRetry) {
                        Text(L10n.retry)
                            .font(Typography.bodyBold)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Color.accent)
                            .cornerRadius(8)
                    }
                }
                
                Button(action: onDismiss) {
                    Text(L10n.dismiss)
                        .font(Typography.bodyBold)
                        .foregroundColor(.ink)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.surfaceElevated)
                        .cornerRadius(8)
                }
            }
        }
        .padding(24)
        .background(Color.cardBackground)
        .cornerRadius(16)
        .shadow(radius: 20)
    }
    
    private var errorIcon: String {
        switch error {
        case .networkUnavailable, .networkTimeout:
            return "wifi.slash"
        case .dataCorrupted, .storageCorrupted:
            return "exclamationmark.triangle.fill"
        case .catalogLoadFailed, .catalogParseFailed:
            return "folder.badge.questionmark"
        case .validationFailed, .invalidInput:
            return "checkmark.circle.fill"
        default:
            return "exclamationmark.circle.fill"
        }
    }
    
    private var errorColor: Color {
        switch error {
        case .networkUnavailable, .networkTimeout:
            return .warning
        case .dataCorrupted, .storageCorrupted:
            return .warning
        case .validationFailed, .invalidInput:
            return .warning
        default:
            return .secondaryText
        }
    }
    
    private var errorTitle: String {
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
}

// MARK: - Preview

#Preview {
    ZStack {
        Color.appScreenBackground
            .ignoresSafeArea()
        
        ErrorAlertView(
            error: .networkUnavailable,
            onDismiss: {},
            onRetry: {}
        )
        .padding()
    }
}
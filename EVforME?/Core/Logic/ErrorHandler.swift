//
//  ErrorHandler.swift
//  EVforME?
//
//  Centralized error handling and reporting system
//

import Foundation
import os.log

/// Central error handler for the application
final class ErrorHandler {
    static let shared = ErrorHandler()
    
    private let logger = Logger(subsystem: "com.evforme.app", category: "ErrorHandler")
    private let errorQueue = DispatchQueue(label: "com.evforme.errorHandler", qos: .utility)
    
    private var recentErrors: [ErrorLog] = []
    private let maxRecentErrors = 50
    
    private init() {}
    
    // MARK: - Public Interface
    
    /// Handle an error with appropriate user feedback
    func handle(_ error: Error, context: ErrorContext = .general, userMessage: String? = nil) {
        let appError = AppError.from(error)
        errorQueue.async { [weak self] in
            self?.logError(appError, context: context)
            self?.storeError(appError, context: context)
            
            // Post notification for UI components to handle
            DispatchQueue.main.async {
                self?.notifyErrorHandled(appError, context: context, userMessage: userMessage)
            }
        }
    }
    
    /// Handle an AppError directly
    func handleAppError(_ error: AppError, context: ErrorContext = .general, userMessage: String? = nil) {
        errorQueue.async { [weak self] in
            self?.logError(error, context: context)
            self?.storeError(error, context: context)
            
            DispatchQueue.main.async {
                self?.notifyErrorHandled(error, context: context, userMessage: userMessage)
            }
        }
    }
    
    /// Handle a result type
    func handleResult<T>(_ result: AppResult<T>, context: ErrorContext = .general, userMessage: String? = nil) {
        switch result {
        case .success:
            break
        case .failure(let error):
            handleAppError(error, context: context, userMessage: userMessage)
        }
    }
    
    // MARK: - Error Reporting
    
    /// Get recent errors for debugging
    func getRecentErrors(limit: Int = 20) -> [ErrorLog] {
        return errorQueue.sync {
            Array(recentErrors.prefix(limit))
        }
    }
    
    /// Clear error history
    func clearErrorHistory() {
        errorQueue.sync {
            recentErrors.removeAll()
        }
    }
    
    /// Get error statistics
    func getErrorStatistics() -> ErrorStatistics {
        return errorQueue.sync {
            let total = recentErrors.count
            let byType = Dictionary(grouping: recentErrors) { $0.errorType }
            let byContext = Dictionary(grouping: recentErrors) { $0.context }
            
            return ErrorStatistics(
                totalErrors: total,
                errorsByType: byType.mapValues { $0.count },
                errorsByContext: Dictionary(uniqueKeysWithValues: byContext.map {
                    (String(describing: $0.key), $0.value.count)
                }),
                lastError: recentErrors.first
            )
        }
    }
    
    // MARK: - Private Methods
    
    private func logError(_ error: AppError, context: ErrorContext) {
        logger.error("Error in \(context.rawValue): \(error.localizedDescription)")
        
        // Log additional context for debugging
        if let recovery = error.recoverySuggestion {
            logger.info("Recovery suggestion: \(recovery)")
        }
        
        #if DEBUG
        logger.debug("Error details - Type: \(type(of: error)), Recoverable: \(error.isRecoverable)")
        #endif
    }
    
    private func storeError(_ error: AppError, context: ErrorContext) {
        // Case name (e.g. "networkUnavailable"), not the type name "AppError".
        let typeKey = String(describing: error).split(separator: "(").first.map(String.init)
            ?? String(describing: error)
        let log = ErrorLog(
            error: error,
            errorType: typeKey,
            context: context,
            timestamp: Date(),
            recoverable: error.isRecoverable
        )

        recentErrors.insert(log, at: 0)
        if recentErrors.count > maxRecentErrors {
            recentErrors.removeLast()
        }
    }
    
    private func notifyErrorHandled(_ error: AppError, context: ErrorContext, userMessage: String?) {
        let notification = ErrorNotification(
            error: error,
            context: context,
            userMessage: userMessage,
            timestamp: Date()
        )
        
        NotificationCenter.default.post(
            name: .errorOccurred,
            object: nil,
            userInfo: ["notification": notification]
        )
    }
}

// MARK: - Supporting Types

/// Context where the error occurred
enum ErrorContext: String {
    case general = "General"
    case network = "Network"
    case catalog = "Catalog"
    case storage = "Storage"
    case validation = "Validation"
    case simulation = "Simulation"
    case ui = "UI"
    case background = "Background"
}

/// Error log entry
struct ErrorLog {
    let error: AppError
    let errorType: String
    let context: ErrorContext
    let timestamp: Date
    let recoverable: Bool
}

/// Error notification for UI components
struct ErrorNotification {
    let error: AppError
    let context: ErrorContext
    let userMessage: String?
    let timestamp: Date
}

/// Error statistics
struct ErrorStatistics {
    let totalErrors: Int
    let errorsByType: [String: Int]
    let errorsByContext: [String: Int]
    let lastError: ErrorLog?
}

// MARK: - Notification Names

extension Notification.Name {
    static let errorOccurred = Notification.Name("com.evforme.errorOccurred")
}

// MARK: - Convenience Extensions

extension Result {
    /// Convert Result to AppResult
    func toAppResult() -> AppResult<Success> where Failure: Error {
        switch self {
        case .success(let value):
            return .success(value)
        case .failure(let error):
            return .failure(AppError.from(error))
        }
    }
}

extension Optional {
    /// Convert Optional to AppResult
    func toAppResult(error: AppError) -> AppResult<Wrapped> {
        switch self {
        case .some(let value):
            return .success(value)
        case .none:
            return .failure(error)
        }
    }
}
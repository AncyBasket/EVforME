//
//  AppError.swift
//  EVforME?
//
//  Sistema centralizzato di error handling per l'applicazione
//

import Foundation

/// Errori specifici del dominio applicativo
enum AppError: LocalizedError, Equatable {
    // MARK: - Network Errors
    case networkUnavailable
    case networkTimeout
    case invalidURL(String)
    case serverError(Int)
    case noDataReceived
    
    // MARK: - Data Errors
    case dataCorrupted
    case dataNotFound
    case invalidDataFormat
    case parsingError(String)
    
    // MARK: - Catalog Errors
    case catalogLoadFailed
    case catalogParseFailed
    case vehicleNotFound(String)
    case catalogOutOfDate
    
    // MARK: - Validation Errors
    case validationFailed([String])
    case invalidInput(String)
    
    // MARK: - Storage Errors
    case storageReadFailed
    case storageWriteFailed
    case storageCorrupted
    
    // MARK: - Service Errors
    case serviceUnavailable(String)
    case configurationError(String)
    
    // MARK: - Cost Service Errors
    case fuelPriceFetchFailed
    case electricityPriceFetchFailed
    case costServiceUnavailable
    
    var errorDescription: String? {
        switch self {
        // Network
        case .networkUnavailable:
            return L10n.errorNetworkUnavailable
        case .networkTimeout:
            return L10n.errorNetworkTimeout
        case .invalidURL(let url):
            return String(format: L10n.errorInvalidURL, url)
        case .serverError(let code):
            return String(format: L10n.errorServerError, code)
        case .noDataReceived:
            return L10n.errorNoDataReceived
            
        // Data
        case .dataCorrupted:
            return L10n.errorDataCorrupted
        case .dataNotFound:
            return L10n.errorDataNotFound
        case .invalidDataFormat:
            return L10n.errorInvalidDataFormat
        case .parsingError(let context):
            return String(format: L10n.errorParsing, context)
            
        // Catalog
        case .catalogLoadFailed:
            return L10n.errorCatalogLoadFailed
        case .catalogParseFailed:
            return L10n.errorCatalogParseFailed
        case .vehicleNotFound(let id):
            return String(format: L10n.errorVehicleNotFound, id)
        case .catalogOutOfDate:
            return L10n.errorCatalogOutOfDate
            
        // Validation
        case .validationFailed(let errors):
            return errors.joined(separator: "\n")
        case .invalidInput(let message):
            return message
            
        // Storage
        case .storageReadFailed:
            return L10n.errorStorageReadFailed
        case .storageWriteFailed:
            return L10n.errorStorageWriteFailed
        case .storageCorrupted:
            return L10n.errorStorageCorrupted
            
        // Service
        case .serviceUnavailable(let service):
            return String(format: L10n.errorServiceUnavailable, service)
        case .configurationError(let config):
            return String(format: L10n.errorConfiguration, config)
            
        // Cost Service
        case .fuelPriceFetchFailed:
            return L10n.errorFuelPriceFetchFailed
        case .electricityPriceFetchFailed:
            return L10n.errorElectricityPriceFetchFailed
        case .costServiceUnavailable:
            return L10n.errorCostServiceUnavailable
        }
    }
    
    var recoverySuggestion: String? {
        switch self {
        case .networkUnavailable, .networkTimeout:
            return L10n.suggestionCheckConnection
        case .catalogLoadFailed, .catalogParseFailed:
            return L10n.suggestionRetryLater
        case .vehicleNotFound:
            return L10n.suggestionSelectAnotherVehicle
        case .storageCorrupted:
            return L10n.suggestionReinstallApp
        default:
            return L10n.suggestionContactSupport
        }
    }
    
    var isRecoverable: Bool {
        switch self {
        case .networkUnavailable, .networkTimeout:
            return true
        case .serverError(let code):
            return code < 500 || code >= 600
        case .fuelPriceFetchFailed, .electricityPriceFetchFailed:
            return true
        case .catalogLoadFailed, .catalogParseFailed:
            return true
        default:
            return false
        }
    }
}

/// Result type custom per operazioni che possono fallire
typealias AppResult<T> = Result<T, AppError>

/// Extension per facilitare la conversione da Error standard
extension AppError {
    static func from(_ error: Error) -> AppError {
        if let appError = error as? AppError {
            return appError
        }
        
        let nsError = error as NSError
        switch nsError.domain {
        case NSURLErrorDomain:
            switch nsError.code {
            case NSURLErrorNotConnectedToInternet, NSURLErrorNetworkConnectionLost:
                return .networkUnavailable
            case NSURLErrorTimedOut:
                return .networkTimeout
            case NSURLErrorBadURL:
                return .invalidURL(nsError.localizedDescription)
            default:
                return .serverError(nsError.code)
            }
        default:
            return .parsingError(nsError.localizedDescription)
        }
    }
}

/// Extension per convertire facilmente URLError in AppError
extension URLError {
    var toAppError: AppError {
        switch self.code {
        case .notConnectedToInternet, .networkConnectionLost, .dnsLookupFailed:
            return .networkUnavailable
        case .timedOut:
            return .networkTimeout
        case .badURL:
            return .invalidURL(self.failureURLString ?? "unknown")
        case .serverCertificateUntrusted, .clientCertificateRejected:
            return .serverError(403)
        default:
            return .serverError(self.code.rawValue)
        }
    }
}
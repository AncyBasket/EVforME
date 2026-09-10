//
//  AppLogger.swift
//  EVforME?
//
//  Sistema di logging strutturato per l'applicazione
//

import Foundation
import os.log

/// Livelli di log personalizzati
enum LogLevel: String, CaseIterable {
    case debug = "DEBUG"
    case info = "INFO"
    case warning = "WARNING"
    case error = "ERROR"
    case critical = "CRITICAL"
    
    var osLogType: OSLogType {
        switch self {
        case .debug: return .debug
        case .info: return .info
        case .warning: return .default
        case .error: return .error
        case .critical: return .fault
        }
    }
    
    var emoji: String {
        switch self {
        case .debug: return "🔍"
        case .info: return "ℹ️"
        case .warning: return "⚠️"
        case .error: return "❌"
        case .critical: return "🚨"
        }
    }
}

/// Categorie di log per organizzazione
enum LogCategory: String {
    case general = "General"
    case network = "Network"
    case catalog = "Catalog"
    case storage = "Storage"
    case validation = "Validation"
    case simulation = "Simulation"
    case ui = "UI"
    case performance = "Performance"
    case analytics = "Analytics"
}

/// Logger strutturato principale
final class AppLogger {
    static let shared = AppLogger()
    
    private let subsystem = "com.evforme.app"
    private var loggers: [LogCategory: Logger] = [:]
    private let logQueue = DispatchQueue(label: "com.evforme.logger", qos: .utility)
    
    // Log storage for in-memory buffering
    private var logBuffer: [LogEntry] = []
    private let maxBufferSize = 500
    private var isBufferingEnabled = false
    
    private init() {
        // Initialize loggers for each category
        for category in LogCategory.allCases {
            loggers[category] = Logger(subsystem: subsystem, category: category.rawValue)
        }
    }
    
    // MARK: - Public Logging Methods
    
    /// Log generico con livello personalizzato
    func log(
        _ level: LogLevel,
        category: LogCategory = .general,
        message: String,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        let logger = loggers[category] ?? loggers[.general]!
        let logMessage = formatMessage(level: level, message: message, function: function, file: file, line: line)
        
        // Send to OSLog
        logger.log(level: level.osLogType, "\(logMessage)")
        
        // Buffer if enabled
        if isBufferingEnabled {
            addToBuffer(level: level, category: category, message: message, function: function, file: file, line: line)
        }
        
        // Print to console in debug mode
        #if DEBUG
        printConsole(level: level, category: category, message: logMessage)
        #endif
    }
    
    /// Log di debug
    func debug(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.debug, category: category, message: message, function: function, file: file, line: line)
    }
    
    /// Log informativo
    func info(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.info, category: category, message: message, function: function, file: file, line: line)
    }
    
    /// Log di warning
    func warning(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.warning, category: category, message: message, function: function, file: file, line: line)
    }
    
    /// Log di errore
    func error(
        _ message: String,
        category: LogCategory = .general,
        error: Error? = nil,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        var fullMessage = message
        if let error = error {
            fullMessage += " | Error: \(error.localizedDescription)"
        }
        log(.error, category: category, message: fullMessage, function: function, file: file, line: line)
    }
    
    /// Log critico
    func critical(
        _ message: String,
        category: LogCategory = .general,
        error: Error? = nil,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        var fullMessage = message
        if let error = error {
            fullMessage += " | Error: \(error.localizedDescription)"
        }
        log(.critical, category: category, message: fullMessage, function: function, file: file, line: line)
    }
    
    // MARK: - Performance Logging
    
    /// Misura e logga il tempo di esecuzione di un'operazione
    func measure<T>(
        _ label: String,
        category: LogCategory = .performance,
        work: () -> T
    ) -> T {
        let startTime = CFAbsoluteTimeGetCurrent()
        let result = work()
        let endTime = CFAbsoluteTimeGetCurrent()
        let duration = (endTime - startTime) * 1000 // Convert to milliseconds
        
        info("\(label) completed in \(String(format: "%.2f", duration))ms", category: category)
        
        return result
    }
    
    /// Misura e logga il tempo di esecuzione di un'operazione async
    func measureAsync<T>(
        _ label: String,
        category: LogCategory = .performance,
        work: () async throws -> T
    ) async rethrows -> T {
        let startTime = CFAbsoluteTimeGetCurrent()
        let result = try await work()
        let endTime = CFAbsoluteTimeGetCurrent()
        let duration = (endTime - startTime) * 1000 // Convert to milliseconds
        
        info("\(label) completed in \(String(format: "%.2f", duration))ms", category: category)
        
        return result
    }
    
    // MARK: - Buffer Management
    
    /// Abilita il buffering dei log in memoria
    func enableBuffering() {
        logQueue.sync {
            isBufferingEnabled = true
        }
    }
    
    /// Disabilita il buffering dei log
    func disableBuffering() {
        logQueue.sync {
            isBufferingEnabled = false
        }
    }
    
    /// Ottieni i log buffered
    func getBufferedLogs(limit: Int = 100) -> [LogEntry] {
        return logQueue.sync {
            Array(logBuffer.prefix(limit))
        }
    }
    
    /// Svuota il buffer dei log
    func clearBuffer() {
        logQueue.sync {
            logBuffer.removeAll()
        }
    }
    
    /// Esporta i log buffered come stringa formattata
    func exportBufferedLogs() -> String {
        let logs = getBufferedLogs()
        return logs.map { entry in
            let timestamp = ISO8601DateFormatter().string(from: entry.timestamp)
            return "[\(timestamp)] [\(entry.level.rawValue)] [\(entry.category.rawValue)] \(entry.message)"
        }.joined(separator: "\n")
    }
    
    // MARK: - Private Methods
    
    private func formatMessage(level: LogLevel, message: String, function: String, file: String, line: Int) -> String {
        let filename = (file as NSString).lastPathComponent
        return "\(level.emoji) [\(filename):\(line)] \(function) - \(message)"
    }
    
    private func printConsole(level: LogLevel, category: LogCategory, message: String) {
        let emoji = level.emoji
        let categoryTag = "[\(category.rawValue)]"
        print("\(emoji) \(categoryTag) \(message)")
    }
    
    private func addToBuffer(
        level: LogLevel,
        category: LogCategory,
        message: String,
        function: String,
        file: String,
        line: Int
    ) {
        let entry = LogEntry(
            level: level,
            category: category,
            message: message,
            function: function,
            file: file,
            line: line,
            timestamp: Date()
        )
        
        logBuffer.insert(entry, at: 0)
        if logBuffer.count > maxBufferSize {
            logBuffer.removeLast()
        }
    }
}

// MARK: - Supporting Types

struct LogEntry {
    let level: LogLevel
    let category: LogCategory
    let message: String
    let function: String
    let file: String
    let line: Int
    let timestamp: Date
}

// MARK: - Convenience Extensions

extension LogCategory {
    static var allCases: [LogCategory] {
        return [
            .general, .network, .catalog, .storage,
            .validation, .simulation, .ui, .performance, .analytics
        ]
    }
}

// MARK: - Usage Examples

/*
 // Basic logging
 AppLogger.shared.info("User started simulation", category: .simulation)
 AppLogger.shared.error("Failed to load catalog", category: .catalog, error: error)
 
 // Performance measurement
 let result = AppLogger.shared.measure("Database query") {
     // Expensive operation
     return performQuery()
 }
 
 // Async performance measurement
 let result = try await AppLogger.shared.measureAsync("API call") {
     return try await fetchData()
 }
 
 // Enable buffering for debugging
 AppLogger.shared.enableBuffering()
 // ... perform operations ...
 let logs = AppLogger.shared.exportBufferedLogs()
 AppLogger.shared.disableBuffering()
 */
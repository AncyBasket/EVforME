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

/// Logger strutturato principale.
/// Uses `os_log` (not `Logger` string interpolation) — `Logger.log("\(msg)")` malloc-abrts
/// on some iOS 18.x Simulator runtimes when the message is freed.
nonisolated final class AppLogger: @unchecked Sendable {
    static let shared = AppLogger()

    private let subsystem = "com.evforme.app"
    private var logs: [LogCategory: OSLog] = [:]
    private let lock = NSLock()

    private var logBuffer: [LogEntry] = []
    private let maxBufferSize = 500
    private var isBufferingEnabled = false

    private init() {
        for category in LogCategory.allCases {
            logs[category] = OSLog(subsystem: subsystem, category: category.rawValue)
        }
    }

    func log(
        _ level: LogLevel,
        category: LogCategory = .general,
        message: String,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        lock.lock()
        defer { lock.unlock() }

        let osLog = logs[category] ?? logs[.general]!
        let logMessage = formatMessage(level: level, message: message, function: function, file: file, line: line)

        os_log("%{public}@", log: osLog, type: level.osLogType, logMessage)

        if isBufferingEnabled {
            addToBufferUnlocked(
                level: level,
                category: category,
                message: message,
                function: function,
                file: file,
                line: line
            )
        }

        #if DEBUG
        printConsole(level: level, category: category, message: logMessage)
        #endif
    }

    func debug(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.debug, category: category, message: message, function: function, file: file, line: line)
    }

    func info(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.info, category: category, message: message, function: function, file: file, line: line)
    }

    func warning(
        _ message: String,
        category: LogCategory = .general,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        log(.warning, category: category, message: message, function: function, file: file, line: line)
    }

    func error(
        _ message: String,
        category: LogCategory = .general,
        error: Error? = nil,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        var fullMessage = message
        if let error {
            fullMessage += " | Error: \(error.localizedDescription)"
        }
        log(.error, category: category, message: fullMessage, function: function, file: file, line: line)
    }

    func critical(
        _ message: String,
        category: LogCategory = .general,
        error: Error? = nil,
        function: String = #function,
        file: String = #file,
        line: Int = #line
    ) {
        var fullMessage = message
        if let error {
            fullMessage += " | Error: \(error.localizedDescription)"
        }
        log(.critical, category: category, message: fullMessage, function: function, file: file, line: line)
    }

    func measure<T>(
        _ label: String,
        category: LogCategory = .performance,
        operation: () throws -> T
    ) rethrows -> T {
        let startTime = CFAbsoluteTimeGetCurrent()
        let result = try operation()
        let duration = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
        info("\(label) completed in \(String(format: "%.2f", duration))ms", category: category)
        return result
    }

    func measureAsync<T>(
        _ label: String,
        category: LogCategory = .performance,
        operation: () async throws -> T
    ) async rethrows -> T {
        let startTime = CFAbsoluteTimeGetCurrent()
        let result = try await operation()
        let duration = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
        info("\(label) completed in \(String(format: "%.2f", duration))ms", category: category)
        return result
    }

    func enableBuffering() {
        lock.lock()
        isBufferingEnabled = true
        lock.unlock()
    }

    func disableBuffering() {
        lock.lock()
        isBufferingEnabled = false
        lock.unlock()
    }

    func getBufferedLogs(limit: Int = 100) -> [LogEntry] {
        lock.lock()
        defer { lock.unlock() }
        return Array(logBuffer.prefix(limit))
    }

    func clearBuffer() {
        lock.lock()
        logBuffer.removeAll()
        lock.unlock()
    }

    func exportBufferedLogs() -> String {
        let logs = getBufferedLogs()
        return logs.map { entry in
            let timestamp = ISO8601DateFormatter().string(from: entry.timestamp)
            return "[\(timestamp)] [\(entry.level.rawValue)] [\(entry.category.rawValue)] \(entry.message)"
        }.joined(separator: "\n")
    }

    private func formatMessage(level: LogLevel, message: String, function: String, file: String, line: Int) -> String {
        let filename = (file as NSString).lastPathComponent
        return "\(level.emoji) [\(filename):\(line)] \(function) - \(message)"
    }

    private func printConsole(level: LogLevel, category: LogCategory, message: String) {
        print("\(level.emoji) [\(category.rawValue)] \(message)")
    }

    private func addToBufferUnlocked(
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

struct LogEntry {
    let level: LogLevel
    let category: LogCategory
    let message: String
    let function: String
    let file: String
    let line: Int
    let timestamp: Date
}

extension LogCategory {
    static var allCases: [LogCategory] {
        [
            .general, .network, .catalog, .storage,
            .validation, .simulation, .ui, .performance, .analytics
        ]
    }
}

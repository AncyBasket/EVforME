//
//  ErrorHandlerTests.swift
//  EVforME?Tests
//
//  Unit tests per il sistema di error handling
//

import XCTest
@testable import EVforME_

final class ErrorHandlerTests: XCTestCase {

    override func setUp() {
        super.setUp()
        ErrorHandler.shared.clearErrorHistory()
    }

    override func tearDown() {
        ErrorHandler.shared.clearErrorHistory()
        super.tearDown()
    }

    // MARK: - Error Handling Tests

    func testHandleError_StoresErrorInHistory() {
        // Given
        let testError = AppError.networkUnavailable

        // When
        ErrorHandler.shared.handleAppError(testError, context: .network)

        // Then
        let recentErrors = ErrorHandler.shared.getRecentErrors(limit: 10)
        XCTAssertEqual(recentErrors.count, 1)
        XCTAssertEqual(recentErrors.first?.errorType, "networkUnavailable")
    }

    func testHandleError_StoresMultipleErrors() {
        // Given
        let errors: [AppError] = [
            .networkUnavailable,
            .catalogLoadFailed,
            .storageCorrupted
        ]

        // When
        for error in errors {
            ErrorHandler.shared.handleAppError(error, context: .general)
        }

        // Then
        let recentErrors = ErrorHandler.shared.getRecentErrors(limit: 10)
        XCTAssertEqual(recentErrors.count, 3)
    }

    func testHandleError_RespectsMaxRecentErrorsLimit() {
        // Given
        let maxErrors = 55 // More than the limit of 50

        // When
        for i in 0..<maxErrors {
            ErrorHandler.shared.handleAppError(.networkUnavailable, context: .general)
        }

        // Then
        let recentErrors = ErrorHandler.shared.getRecentErrors()
        XCTAssertLessThanOrEqual(recentErrors.count, 50)
    }

    func testGetRecentErrors_LimitParameter() {
        // Given
        for _ in 0..<10 {
            ErrorHandler.shared.handleAppError(.networkUnavailable, context: .general)
        }

        // When
        let limitedErrors = ErrorHandler.shared.getRecentErrors(limit: 5)

        // Then
        XCTAssertEqual(limitedErrors.count, 5)
    }

    func testClearErrorHistory_RemovesAllErrors() {
        // Given
        ErrorHandler.shared.handleAppError(.networkUnavailable, context: .network)
        ErrorHandler.shared.handleAppError(.catalogLoadFailed, context: .catalog)

        // When
        ErrorHandler.shared.clearErrorHistory()

        // Then
        let recentErrors = ErrorHandler.shared.getRecentErrors()
        XCTAssertTrue(recentErrors.isEmpty)
    }

    // MARK: - Error Statistics Tests

    func testGetErrorStatistics_ReturnsCorrectCounts() {
        // Given
        ErrorHandler.shared.handleAppError(.networkUnavailable, context: .network)
        ErrorHandler.shared.handleAppError(.catalogLoadFailed, context: .catalog)
        ErrorHandler.shared.handleAppError(.networkUnavailable, context: .network)

        // When
        let stats = ErrorHandler.shared.getErrorStatistics()

        // Then
        XCTAssertEqual(stats.totalErrors, 3)
        XCTAssertEqual(stats.errorsByType["networkUnavailable"], 2)
        XCTAssertEqual(stats.errorsByType["catalogLoadFailed"], 1)
        XCTAssertEqual(stats.errorsByContext["network"], 2)
        XCTAssertEqual(stats.errorsByContext["catalog"], 1)
    }

    func testGetErrorStatistics_IncludesLastError() {
        // Given
        let testError = AppError.storageCorrupted
        ErrorHandler.shared.handleAppError(testError, context: .storage)

        // When
        let stats = ErrorHandler.shared.getErrorStatistics()

        // Then
        XCTAssertNotNil(stats.lastError)
        XCTAssertEqual(stats.lastError?.context, .storage)
    }

    // MARK: - Error Conversion Tests

    func testAppErrorFromURLError_NetworkUnavailable() {
        // Given
        let urlError = URLError(.notConnectedToInternet)

        // When
        let appError = AppError.from(urlError)

        // Then
        XCTAssertEqual(appError, AppError.networkUnavailable)
    }

    func testAppErrorFromURLError_Timeout() {
        // Given
        let urlError = URLError(.timedOut)

        // When
        let appError = AppError.from(urlError)

        // Then
        XCTAssertEqual(appError, AppError.networkTimeout)
    }

    func testAppErrorFromURLError_BadURL() {
        // Given
        let urlError = URLError(.badURL)

        // When
        let appError = AppError.from(urlError)

        // Then
        if case .invalidURL = appError {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected invalidURL error")
        }
    }

    func testAppErrorFromStandardError() {
        // Given
        let nsError = NSError(domain: "test.domain", code: 100)

        // When
        let appError = AppError.from(nsError)

        // Then
        if case .parsingError = appError {
            XCTAssertTrue(true)
        } else {
            XCTFail("Expected parsingError for unknown errors")
        }
    }

    // MARK: - Error Properties Tests

    func testNetworkError_IsRecoverable() {
        // Given
        let error = AppError.networkUnavailable

        // Then
        XCTAssertTrue(error.isRecoverable)
    }

    func testServerError_Below500_IsRecoverable() {
        // Given
        let error = AppError.serverError(404)

        // Then
        XCTAssertTrue(error.isRecoverable)
    }

    func testServerError_Above500_IsNotRecoverable() {
        // Given
        let error = AppError.serverError(500)

        // Then
        XCTAssertFalse(error.isRecoverable)
    }

    func testStorageCorrupted_IsNotRecoverable() {
        // Given
        let error = AppError.storageCorrupted

        // Then
        XCTAssertFalse(error.isRecoverable)
    }

    func testError_HasRecoverySuggestion() {
        // Given
        let error = AppError.networkUnavailable

        // Then
        XCTAssertNotNil(error.recoverySuggestion)
        XCTAssertFalse(error.recoverySuggestion!.isEmpty)
    }

    func testError_HasDescription() {
        // Given
        let error = AppError.catalogLoadFailed

        // Then
        XCTAssertNotNil(error.errorDescription)
        XCTAssertFalse(error.errorDescription!.isEmpty)
    }

    // MARK: - Result Type Tests

    func testResultToAppResult_Success() {
        // Given
        let result: Result<String, Error> = .success("test")

        // When
        let appResult = result.toAppResult()

        // Then
        if case .success(let value) = appResult {
            XCTAssertEqual(value, "test")
        } else {
            XCTFail("Expected success")
        }
    }

    func testResultToAppResult_Failure() {
        // Given
        let result: Result<String, Error> = .failure(URLError(.timedOut))

        // When
        let appResult = result.toAppResult()

        // Then
        if case .failure(let error) = appResult {
            XCTAssertEqual(error, AppError.networkTimeout)
        } else {
            XCTFail("Expected failure")
        }
    }

    func testOptionalToAppResult_Some() {
        // Given
        let optional: String? = "test"

        // When
        let result = optional.toAppResult(error: .dataNotFound)

        // Then
        if case .success(let value) = result {
            XCTAssertEqual(value, "test")
        } else {
            XCTFail("Expected success")
        }
    }

    func testOptionalToAppResult_None() {
        // Given
        let optional: String? = nil

        // When
        let result = optional.toAppResult(error: .dataNotFound)

        // Then
        if case .failure(let error) = result {
            XCTAssertEqual(error, AppError.dataNotFound)
        } else {
            XCTFail("Expected failure")
        }
    }
}
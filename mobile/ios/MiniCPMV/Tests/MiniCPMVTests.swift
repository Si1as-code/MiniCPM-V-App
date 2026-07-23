import XCTest
import CoreData
@testable import MiniCPMV

/**
 * MiniCPM-V iOS 单元测试
 *
 * 覆盖模块:
 * - Core Data 实体
 * - Keychain 存取
 * - API 数据模型
 * - 工具方法
 */
final class MiniCPMVTests: XCTestCase {

    // MARK: - Core Data Tests

    func testRecognitionRecordCreation() {
        let context = createTestContext()
        let record = RecognitionRecordEntity.create(
            in: context,
            imageHash: "test_hash_001",
            imagePath: "/path/to/image.jpg",
            question: "这是什么？",
            answer: "这是一只猫",
            confidence: 0.92
        )

        XCTAssertEqual(record.imageHash, "test_hash_001")
        XCTAssertEqual(record.question, "这是什么？")
        XCTAssertEqual(record.answer, "这是一只猫")
        XCTAssertEqual(record.confidence, 0.92, accuracy: 0.01)
        XCTAssertEqual(record.modelVersion, "4.6")
        XCTAssertEqual(record.taskType, "local")
        XCTAssertFalse(record.synced)
        XCTAssertNotNil(record.createdAt)
        XCTAssertNotNil(record.updatedAt)
    }

    func testConversationCreation() {
        let context = createTestContext()
        let recordId = UUID()
        let conversation = ConversationEntity.create(
            in: context,
            recordId: recordId,
            role: "user",
            content: "描述这张图片"
        )

        XCTAssertEqual(conversation.recordId, recordId)
        XCTAssertEqual(conversation.role, "user")
        XCTAssertEqual(conversation.content, "描述这张图片")
        XCTAssertEqual(conversation.tokenCount, 0)
    }

    // MARK: - UserSetting Tests

    func testUserSettingSetAndGet() {
        let context = createTestContext()

        UserSettingEntity.set("test_key", value: "test_value", in: context)
        let value = UserSettingEntity.get("test_key", in: context)

        XCTAssertEqual(value, "test_value")
    }

    func testUserSettingBoolConversion() {
        let context = createTestContext()

        UserSettingEntity.set("bool_key", value: "true", in: context)
        XCTAssertTrue(UserSettingEntity.getBool("bool_key", in: context))

        UserSettingEntity.set("bool_key", value: "false", in: context)
        XCTAssertFalse(UserSettingEntity.getBool("bool_key", in: context))
    }

    func testSettingKeysAreUnique() {
        let keys = [
            SettingKeys.autoRecognition,
            SettingKeys.cloudEnabled,
            SettingKeys.dailyBudget,
            SettingKeys.confidenceThreshold,
            SettingKeys.syncWifiOnly
        ]
        XCTAssertEqual(keys.count, Set(keys).count, "设置键名不应重复")
    }

    // MARK: - Keychain Tests

    func testKeychainSaveAndLoad() {
        let manager = KeychainManager()
        let testValue = "test_token_abc123"

        manager.save(.accessToken, value: testValue)
        let loaded = manager.load(.accessToken)

        XCTAssertEqual(loaded, testValue)

        // 清理
        manager.delete(.accessToken)
    }

    func testKeychainDelete() {
        let manager = KeychainManager()

        manager.save(.userId, value: "user123")
        XCTAssertTrue(manager.exists(.userId))

        manager.delete(.userId)
        XCTAssertFalse(manager.exists(.userId))
    }

    // MARK: - API Model Tests

    func testInferenceRequestEncoding() {
        let request = InferenceRequest(
            imageBase64: "base64data",
            question: "描述这张图片",
            modelVersion: "4.6",
            forceLocal: false
        )

        XCTAssertEqual(request.imageBase64, "base64data")
        XCTAssertEqual(request.question, "描述这张图片")
        XCTAssertEqual(request.modelVersion, "4.6")
        XCTAssertFalse(request.forceLocal)
    }

    func testInferenceResponseDecoding() throws {
        let json = """
        {
            "answer": "这是一只猫",
            "confidence": 0.92,
            "model_version": "4.6",
            "latency_ms": 1234,
            "task_type": "local"
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(InferenceResponse.self, from: json)

        XCTAssertEqual(response.answer, "这是一只猫")
        XCTAssertEqual(response.confidence, 0.92, accuracy: 0.01)
        XCTAssertEqual(response.modelVersion, "4.6")
        XCTAssertEqual(response.latencyMs, 1234)
        XCTAssertEqual(response.taskType, "local")
    }

    func testSyncResponseDecoding() throws {
        let json = """
        {
            "uploaded": 10,
            "conflicts": 2,
            "message": "同步完成"
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(SyncResponse.self, from: json)

        XCTAssertEqual(response.uploaded, 10)
        XCTAssertEqual(response.conflicts, 2)
        XCTAssertEqual(response.message, "同步完成")
    }

    // MARK: - InferenceResult Tests

    func testInferenceResultSuccess() {
        let result = InferenceResult(
            answer: "识别成功",
            confidence: 0.85,
            latencyMs: 500,
            modelVersion: "4.6-coreml",
            success: true
        )

        XCTAssertTrue(result.success)
        XCTAssertEqual(result.answer, "识别成功")
        XCTAssertEqual(result.confidence, 0.85, accuracy: 0.01)
        XCTAssertNil(result.errorMessage)
    }

    func testInferenceResultFailure() {
        let result = InferenceResult(
            answer: "推理失败",
            confidence: 0,
            latencyMs: 0,
            modelVersion: "",
            success: false,
            errorMessage: "模型未加载"
        )

        XCTAssertFalse(result.success)
        XCTAssertEqual(result.errorMessage, "模型未加载")
    }

    // MARK: - Confidence Calculation

    func testConfidenceToPercentage() {
        let confidence: Float = 0.85
        let percentage = Int(confidence * 100)
        XCTAssertEqual(percentage, 85)
    }

    // MARK: - SyncState Tests

    func testSyncStateEquality() {
        XCTAssertEqual(SyncState.idle, SyncState.idle)
        XCTAssertEqual(SyncState.syncing, SyncState.syncing)
        XCTAssertNotEqual(SyncState.idle, SyncState.syncing)
        XCTAssertEqual(SyncState.success(message: "OK"), SyncState.success(message: "OK"))
        XCTAssertEqual(SyncState.error(message: "Fail"), SyncState.error(message: "Fail"))
    }

    // MARK: - Helper

    private func createTestContext() -> NSManagedObjectContext {
        let model = CoreDataModelBuilder.createModel()
        let container = NSPersistentContainer(name: "TestModel", managedObjectModel: model)

        let description = NSPersistentStoreDescription()
        description.type = NSInMemoryStoreType
        container.persistentStoreDescriptions = [description]

        container.loadPersistentStores { _, _ in }
        return container.viewContext
    }
}

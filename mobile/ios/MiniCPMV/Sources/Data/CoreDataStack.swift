import CoreData
import Foundation

/**
 * Core Data 持久化栈
 *
 * 职责:
 * - 管理 NSPersistentContainer（Core Data 栈）
 * - 配置 Data Protection 加密（NSFileProtectionComplete）
 * - 提供线程安全的 NSManagedObjectContext
 * - 处理数据迁移
 *
 * 对应 Android 端的 AppDatabase.kt (Room + SQLCipher)
 *
 * iOS 数据保护策略:
 * - NSFileProtectionComplete: 设备锁定后文件无法访问（最高级别）
 * - NSFileProtectionCompleteUnlessOpen: 锁定后已打开的文件可继续访问
 * - NSFileProtectionCompleteUntilFirstUserAuthentication: 首次解锁后可访问
 */
final class CoreDataStack: ObservableObject {

    static let shared = CoreDataStack()

    // MARK: - Properties

    private let containerName = "MiniCPMVModel"
    private(set) lazy var container: NSPersistentContainer = {
        let container = NSPersistentContainer(name: containerName)

        // 配置 Data Protection
        let description = container.persistentStoreDescriptions.first
        description?.setOption(
            FileProtectionType.completeUntilFirstUserAuthentication as NSObject,
            forKey: NSPersistentStoreFileProtectionKey
        )
        description?.shouldMigrateStoreAutomatically = true
        description?.shouldInferMappingModelAutomatically = true

        container.loadPersistentStores { _, error in
            if let error = error as NSError? {
                print("[CoreData] 加载失败: \(error), \(error.userInfo)")
            }
        }

        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy

        return container
    }()

    var viewContext: NSManagedObjectContext {
        container.viewContext
    }

    // MARK: - Initialization

    private init() {}

    // MARK: - Background Context

    /**
     * 创建后台上下文（用于耗时操作）
     */
    func newBackgroundContext() -> NSManagedObjectContext {
        let context = container.newBackgroundContext()
        context.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
        return context
    }

    // MARK: - Save

    /**
     * 保存上下文
     */
    func save(context: NSManagedObjectContext? = nil) {
        let ctx = context ?? viewContext
        guard ctx.hasChanges else { return }

        do {
            try ctx.save()
        } catch {
            print("[CoreData] 保存失败: \(error.localizedDescription)")
        }
    }

    // MARK: - Data Protection

    /**
     * 检查 Data Protection 状态
     */
    func checkDataProtectionStatus() -> FileProtectionType? {
        guard let storeURL = container.persistentStoreDescriptions.first?.url else {
            return nil
        }
        return try? FileManager.default.attributesOfItem(atPath: storeURL.path)
            [.protectionKey] as? FileProtectionType
    }

    /**
     * 获取数据库文件路径
     */
    func getStoreURL() -> URL? {
        container.persistentStoreDescriptions.first?.url
    }

    // MARK: - Batch Operations

    /**
     * 批量删除旧数据
     */
    func deleteRecordsOlderThan(timestamp: Date) {
        let request: NSFetchRequest<NSFetchRequestResult> = NSFetchRequest(entityName: "RecognitionRecordEntity")
        request.predicate = NSPredicate(format: "createdAt < %@", timestamp as NSDate)

        let batchDelete = NSBatchDeleteRequest(fetchRequest: request)

        do {
            try container.viewContext.execute(batchDelete)
            save()
        } catch {
            print("[CoreData] 批量删除失败: \(error.localizedDescription)")
        }
    }
}

// MARK: - Core Data Entity Extensions

/**
 * 识别记录实体扩展
 * 对应 Android 的 RecognitionRecord
 */
extension RecognitionRecordEntity {
    // 便捷创建方法
    static func create(
        in context: NSManagedObjectContext,
        imageHash: String,
        imagePath: String,
        question: String,
        answer: String,
        confidence: Float,
        taskType: String = "local"
    ) -> RecognitionRecordEntity {
        let entity = RecognitionRecordEntity(context: context)
        entity.id = UUID()
        entity.imageHash = imageHash
        entity.imagePath = imagePath
        entity.question = question
        entity.answer = answer
        entity.confidence = confidence
        entity.modelVersion = "4.6"
        entity.deviceId = UIDevice.current.identifierForVendor?.uuidString ?? ""
        entity.taskType = taskType
        entity.synced = false
        entity.createdAt = Date()
        entity.updatedAt = Date()
        return entity
    }
}

/**
 * 对话消息实体扩展
 * 对应 Android 的 Conversation
 */
extension ConversationEntity {
    static func create(
        in context: NSManagedObjectContext,
        recordId: UUID,
        role: String,
        content: String,
        tokenCount: Int = 0
    ) -> ConversationEntity {
        let entity = ConversationEntity(context: context)
        entity.id = UUID()
        entity.recordId = recordId
        entity.role = role
        entity.content = content
        entity.tokenCount = Int32(tokenCount)
        entity.createdAt = Date()
        return entity
    }
}

/**
 * 用户设置实体扩展
 * 对应 Android 的 UserSetting
 */
extension UserSettingEntity {
    static func get(_ key: String, in context: NSManagedObjectContext) -> String? {
        let request: NSFetchRequest<UserSettingEntity> = NSFetchRequest(entityName: "UserSettingEntity")
        request.predicate = NSPredicate(format: "key == %@", key)
        request.fetchLimit = 1
        return try? context.fetch(request).first?.value
    }

    static func set(_ key: String, value: String, in context: NSManagedObjectContext) {
        let request: NSFetchRequest<UserSettingEntity> = NSFetchRequest(entityName: "UserSettingEntity")
        request.predicate = NSPredicate(format: "key == %@", key)
        request.fetchLimit = 1

        if let existing = try? context.fetch(request).first {
            existing.value = value
            existing.updatedAt = Date()
        } else {
            let entity = UserSettingEntity(context: context)
            entity.key = key
            entity.value = value
            entity.updatedAt = Date()
        }
    }

    static func getBool(_ key: String, default: Bool = false, in context: NSManagedObjectContext) -> Bool {
        get(key, in: context)?.lowercased() == "true" ?? `default`
    }

    static func getFloat(_ key: String, default: Float = 0, in context: NSManagedObjectContext) -> Float {
        Float(get(key, in: context) ?? "") ?? `default`
    }
}

// 设置键名常量（与 Android 端保持一致）
enum SettingKeys {
    static let autoRecognition = "auto_recognition"
    static let cloudEnabled = "cloud_enabled"
    static let dailyBudget = "daily_budget"
    static let confidenceThreshold = "confidence_threshold"
    static let syncWifiOnly = "sync_wifi_only"
    static let lastSyncTime = "last_sync_time"
}

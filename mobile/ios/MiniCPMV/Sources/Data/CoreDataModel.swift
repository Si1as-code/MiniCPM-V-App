import CoreData
import Foundation

/**
 * Core Data 模型定义（程序化定义，替代 .xcdatamodeld）
 *
 * 当无法使用 Xcode 可视化编辑器时，通过代码定义 Entity
 * 对应 3 张表：
 * 1. RecognitionRecordEntity - 识别记录
 * 2. ConversationEntity - 对话消息
 * 3. UserSettingEntity - 用户设置
 */
enum CoreDataModelBuilder {

    static func createModel() -> NSManagedObjectModel {
        let model = NSManagedObjectModel()

        // 1. 识别记录实体
        let recordEntity = NSEntityDescription()
        recordEntity.name = "RecognitionRecordEntity"
        recordEntity.managedObjectClassName = "RecognitionRecordEntity"

        recordEntity.properties = [
            attribute(name: "id", type: .UUIDAttributeType, optional: false),
            attribute(name: "imageHash", type: .stringAttributeType, optional: false),
            attribute(name: "imagePath", type: .stringAttributeType, optional: true),
            attribute(name: "question", type: .stringAttributeType, optional: false),
            attribute(name: "answer", type: .stringAttributeType, optional: false),
            attribute(name: "confidence", type: .floatAttributeType, optional: false),
            attribute(name: "modelVersion", type: .stringAttributeType, optional: false, defaultValue: "4.6"),
            attribute(name: "deviceId", type: .stringAttributeType, optional: true),
            attribute(name: "taskType", type: .stringAttributeType, optional: false, defaultValue: "local"),
            attribute(name: "synced", type: .booleanAttributeType, optional: false, defaultValue: false),
            attribute(name: "createdAt", type: .dateAttributeType, optional: false),
            attribute(name: "updatedAt", type: .dateAttributeType, optional: false)
        ]

        // 2. 对话消息实体
        let conversationEntity = NSEntityDescription()
        conversationEntity.name = "ConversationEntity"
        conversationEntity.managedObjectClassName = "ConversationEntity"

        conversationEntity.properties = [
            attribute(name: "id", type: .UUIDAttributeType, optional: false),
            attribute(name: "recordId", type: .UUIDAttributeType, optional: false),
            attribute(name: "role", type: .stringAttributeType, optional: false),
            attribute(name: "content", type: .stringAttributeType, optional: false),
            attribute(name: "tokenCount", type: .integer32AttributeType, optional: false, defaultValue: 0),
            attribute(name: "createdAt", type: .dateAttributeType, optional: false)
        ]

        // 3. 用户设置实体
        let settingEntity = NSEntityDescription()
        settingEntity.name = "UserSettingEntity"
        settingEntity.managedObjectClassName = "UserSettingEntity"

        settingEntity.properties = [
            attribute(name: "key", type: .stringAttributeType, optional: false),
            attribute(name: "value", type: .stringAttributeType, optional: false),
            attribute(name: "updatedAt", type: .dateAttributeType, optional: false)
        ]

        model.entities = [recordEntity, conversationEntity, settingEntity]
        return model
    }

    private static func attribute(
        name: String,
        type: NSAttributeType,
        optional: Bool = true,
        defaultValue: Any? = nil
    ) -> NSAttributeDescription {
        let attr = NSAttributeDescription()
        attr.name = name
        attr.attributeType = type
        attr.isOptional = optional
        if let defaultValue = defaultValue {
            attr.defaultValue = defaultValue
        }
        return attr
    }
}

// MARK: - Core Data Entity Classes

/**
 * 识别记录实体
 * 对应 Android 的 RecognitionRecord
 */
@objc(RecognitionRecordEntity)
final class RecognitionRecordEntity: NSManagedObject {
    @NSManaged var id: UUID
    @NSManaged var imageHash: String
    @NSManaged var imagePath: String?
    @NSManaged var question: String
    @NSManaged var answer: String
    @NSManaged var confidence: Float
    @NSManaged var modelVersion: String
    @NSManaged var deviceId: String?
    @NSManaged var taskType: String
    @NSManaged var synced: Bool
    @NSManaged var createdAt: Date
    @NSManaged var updatedAt: Date
}

/**
 * 对话消息实体
 * 对应 Android 的 Conversation
 */
@objc(ConversationEntity)
final class ConversationEntity: NSManagedObject {
    @NSManaged var id: UUID
    @NSManaged var recordId: UUID
    @NSManaged var role: String
    @NSManaged var content: String
    @NSManaged var tokenCount: Int32
    @NSManaged var createdAt: Date
}

/**
 * 用户设置实体
 * 对应 Android 的 UserSetting
 */
@objc(UserSettingEntity)
final class UserSettingEntity: NSManagedObject {
    @NSManaged var key: String
    @NSManaged var value: String
    @NSManaged var updatedAt: Date
}

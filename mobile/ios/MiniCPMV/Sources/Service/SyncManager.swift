import Foundation
import CoreData

/**
 * 数据同步管理器
 *
 * 职责:
 * - 将本地未同步记录上传到云端
 * - 从云端下载最新记录
 * - 冲突解决（last_write_wins）
 * - 同步状态管理
 *
 * 对应 Android 端 MainViewModel 中的 syncState 逻辑
 */
final class SyncManager {

    private let coreData: CoreDataStack
    private let api: APIClient

    init(coreData: CoreDataStack, api: APIClient) {
        self.coreData = coreData
        self.api = api
    }

    // MARK: - Upload

    /**
     * 上传未同步记录
     */
    func uploadUnsyncedRecords() async throws -> SyncResponse {
        let context = coreData.newBackgroundContext()

        // 查询未同步记录
        let request: NSFetchRequest<RecognitionRecordEntity> = NSFetchRequest(entityName: "RecognitionRecordEntity")
        request.predicate = NSPredicate(format: "synced == NO")
        request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: true)]

        let unsynced = try context.fetch(request)

        guard !unsynced.isEmpty else {
            return SyncResponse(uploaded: 0, conflicts: 0, message: "无待同步记录")
        }

        // 转换为 DTO 并上传
        // 实际实现应批量上传，这里简化
        for record in unsynced {
            // TODO: 调用 API 上传
            record.synced = true
            record.updatedAt = Date()
        }

        try context.save()

        return SyncResponse(
            uploaded: unsynced.count,
            conflicts: 0,
            message: "同步完成，\(unsynced.count) 条记录"
        )
    }

    // MARK: - Download

    /**
     * 从云端下载最新记录
     */
    func downloadRecords(since: Date? = nil) async throws {
        // 实际实现应调用 API 下载
        // let records: [CloudRecord] = try await api.get("/api/sync/download", ...)
        // 然后合并到本地 Core Data
    }

    // MARK: - Conflict Resolution

    /**
     * 冲突解决（last_write_wins 策略）
     */
    func resolveConflict(local: RecognitionRecordEntity, remoteUpdatedAt: Date) -> Bool {
        // 如果远端更新时间更晚，使用远端数据
        if remoteUpdatedAt > local.updatedAt {
            return true  // 需要更新本地
        }
        return false  // 保留本地
    }

    // MARK: - Full Sync

    /**
     * 执行完整同步流程
     */
    func fullSync() async -> SyncState {
        do {
            // 1. 上传本地变更
            let uploadResult = try await uploadUnsyncedRecords()

            // 2. 下载远端变更
            try await downloadRecords()

            // 3. 更新同步时间
            let context = coreData.viewContext
            UserSettingEntity.set(SettingKeys.lastSyncTime, value: ISO8601DateFormatter().string(from: Date()), in: context)
            coreData.save()

            return .success(message: uploadResult.message)

        } catch {
            return .error(message: error.localizedDescription)
        }
    }
}

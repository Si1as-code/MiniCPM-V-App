import BackgroundTasks
import Foundation

/**
 * BGTaskScheduler 后台任务调度器
 *
 * 职责:
 * - 注册后台任务标识符
 * - 调度定期识别任务（BGAppRefreshTask）
 * - 调度同步任务（BGProcessingTask）
 * - 处理任务执行和结果回调
 *
 * 对应 Android 端的 RecognitionForegroundService
 *
 * iOS 后台任务类型:
 * - BGAppRefreshTask: 短时任务（约 30 秒），适合轻量刷新
 * - BGProcessingTask: 长时任务（可达数分钟），适合重度处理，需在充电时执行
 */
final class BackgroundTaskScheduler: ObservableObject {

    // MARK: - Task Identifiers

    static let recognitionTaskId = "com.minicpmv.app.recognition"
    static let syncTaskId = "com.minicpmv.app.sync"

    // MARK: - Published State

    @Published var isRecognitionScheduled = false
    @Published var lastRecognitionTime: Date? = nil
    @Published var lastSyncTime: Date? = nil

    // MARK: - Registration

    /**
     * 注册后台任务
     * 必须在 App 启动时调用（applicationDidFinishLaunching 阶段）
     */
    func registerTasks() {
        // 注册识别任务（BGAppRefreshTask）
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.recognitionTaskId,
            using: nil
        ) { [weak self] task in
            self?.handleRecognitionTask(task as! BGAppRefreshTask)
        }

        // 注册同步任务（BGProcessingTask）
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.syncTaskId,
            using: nil
        ) { [weak self] task in
            self?.handleSyncTask(task as! BGProcessingTask)
        }

        print("[BGTask] 后台任务已注册")
    }

    // MARK: - Scheduling

    /**
     * 调度后台识别任务
     *
     * - Parameter interval: 下次执行间隔（最小 15 分钟）
     */
    func scheduleRecognitionTask(after interval: TimeInterval = 15 * 60) {
        let request = BGAppRefreshTaskRequest(identifier: Self.recognitionTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: interval)

        do {
            try BGTaskScheduler.shared.submit(request)
            DispatchQueue.main.async {
                self.isRecognitionScheduled = true
            }
            print("[BGTask] 识别任务已调度，\(Int(interval/60)) 分钟后执行")
        } catch {
            print("[BGTask] 调度识别任务失败: \(error.localizedDescription)")
        }
    }

    /**
     * 调度后台同步任务
     *
     * - Parameter interval: 下次执行间隔
     * - Parameter requiresNetwork: 是否需要网络
     * - Parameter requiresExternalPower: 是否需要充电
     */
    func scheduleSyncTask(
        after interval: TimeInterval = 30 * 60,
        requiresNetwork: Bool = true,
        requiresExternalPower: Bool = false
    ) {
        let request = BGProcessingTaskRequest(identifier: Self.syncTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: interval)
        request.requiresNetworkConnectivity = requiresNetwork
        request.requiresExternalPower = requiresExternalPower

        do {
            try BGTaskScheduler.shared.submit(request)
            print("[BGTask] 同步任务已调度")
        } catch {
            print("[BGTask] 调度同步任务失败: \(error.localizedDescription)")
        }
    }

    // MARK: - Task Handlers

    /**
     * 处理后台识别任务
     */
    private func handleRecognitionTask(_ task: BGAppRefreshTask) {
        print("[BGTask] 后台识别任务开始执行")

        // 安排下一次执行
        scheduleRecognitionTask()

        // 创建任务超时句柄
        task.expirationHandler = {
            task.setTaskCompleted(success: false)
            print("[BGTask] 识别任务超时")
        }

        // 在后台执行识别
        // 注意: iOS 后台无法直接使用相机，这里执行已缓存图片的识别或云端推理
        Task {
            let success = await performBackgroundRecognition()
            await MainActor.run {
                task.setTaskCompleted(success: success)
                self.lastRecognitionTime = Date()
                self.isRecognitionScheduled = false
            }
        }
    }

    /**
     * 处理后台同步任务
     */
    private func handleSyncTask(_ task: BGProcessingTask) {
        print("[BGTask] 后台同步任务开始执行")

        scheduleSyncTask()

        task.expirationHandler = {
            task.setTaskCompleted(success: false)
        }

        Task {
            let success = await performBackgroundSync()
            await MainActor.run {
                task.setTaskCompleted(success: success)
                self.lastSyncTime = Date()
            }
        }
    }

    // MARK: - Task Execution

    /**
     * 执行后台识别
     */
    private func performBackgroundRecognition() async -> Bool {
        // iOS 后台无法使用相机，这里执行云端推理或处理缓存
        // 实际实现应检查是否有待处理的图片
        print("[BGTask] 执行后台识别...")
        try? await Task.sleep(nanoseconds: 2_000_000_000)  // 模拟处理
        return true
    }

    /**
     * 执行后台同步
     */
    private func performBackgroundSync() async -> Bool {
        print("[BGTask] 执行后台同步...")
        // 实际实现应调用 SyncManager
        try? await Task.sleep(nanoseconds: 3_000_000_000)
        return true
    }

    // MARK: - Cancel

    /**
     * 取消所有待执行的后台任务
     */
    func cancelAll() {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.recognitionTaskId)
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.syncTaskId)
        DispatchQueue.main.async {
            self.isRecognitionScheduled = false
        }
        print("[BGTask] 所有后台任务已取消")
    }
}

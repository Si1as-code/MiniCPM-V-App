import SwiftUI

/**
 * MiniCPM-V iOS 应用入口
 *
 * 职责:
 * - 初始化 Core Data 栈（Data Protection 加密）
 * - 注册 BGTaskScheduler 后台任务
 * - 预加载 Core ML 推理引擎
 * - 配置 SwiftUI TabView 导航
 */
@main
struct MiniCPMVApp: App {
    // 使用 @StateObject 确保整个应用生命周期内唯一实例
    @StateObject private var appState = AppState()

    // 后台任务调度器
    @StateObject private var backgroundScheduler = BackgroundTaskScheduler()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(backgroundScheduler)
                .preferredColorScheme(appState.colorScheme)
                .onAppear {
                    // 注册后台任务
                    backgroundScheduler.registerTasks()
                    // 预加载推理引擎
                    appState.inferenceEngine.warmup()
                }
        }
    }
}

/**
 * 全局应用状态
 *
 * 持有 Core Data 栈、推理引擎、Keychain 管理器等核心组件
 */
final class AppState: ObservableObject {
    let coreDataStack: CoreDataStack
    let inferenceEngine: CoreMLInferenceEngine
    let keychainManager: KeychainManager
    let apiClient: APIClient
    let syncManager: SyncManager

    @Published var colorScheme: ColorScheme? = nil  // nil = 跟随系统

    // 用户认证状态
    @Published var isAuthenticated: Bool = false
    @Published var currentUser: User? = nil

    // 推理状态
    @Published var isInferencing: Bool = false
    @Published var lastResult: InferenceResult? = nil

    // 同步状态
    @Published var syncState: SyncState = .idle

    init() {
        self.coreDataStack = CoreDataStack.shared
        self.inferenceEngine = CoreMLInferenceEngine()
        self.keychainManager = KeychainManager()
        self.apiClient = APIClient(keychain: keychainManager)
        self.syncManager = SyncManager(coreData: coreDataStack, api: apiClient)

        // 从 Keychain 恢复登录状态
        if let token = keychainManager.load(.accessToken), !token.isEmpty {
            self.isAuthenticated = true
            self.currentUser = User(id: keychainManager.load(.userId), token: token)
        }
    }
}

/**
 * 用户模型
 */
struct User: Identifiable {
    let id: String
    let token: String
    var refreshToken: String? = nil
}

/**
 * 同步状态机
 */
enum SyncState: Equatable {
    case idle
    case syncing
    case success(message: String)
    case error(message: String)
}

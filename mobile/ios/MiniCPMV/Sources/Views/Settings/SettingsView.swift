import SwiftUI

/**
 * 设置页面
 *
 * 功能:
 * - 识别设置（自动识别开关、置信度阈值）
 * - 云端设置（云端 API 开关、日预算）
 * - 同步设置（仅 WiFi 同步、手动同步）
 * - 安全设置（Data Protection、Keychain）
 * - 后台任务管理
 *
 * 对应 Android 端的 SettingsScreen.kt
 */
struct SettingsView: View {

    @EnvironmentObject var appState: AppState
    @EnvironmentObject var backgroundScheduler: BackgroundTaskScheduler

    @State private var autoRecognition = false
    @State private var cloudEnabled = false
    @State private var syncWifiOnly = true
    @State private var confidenceThreshold: Double = 0.7
    @State private var dailyBudget: Double = 10

    var body: some View {
        NavigationStack {
            Form {
                // 识别设置
                Section("识别") {
                    Toggle("后台自动识别", isOn: $autoRecognition)
                        .onChange(of: autoRecognition) { _, newValue in
                            saveSetting(SettingKeys.autoRecognition, value: String(newValue))
                            if newValue {
                                backgroundScheduler.scheduleRecognitionTask()
                            } else {
                                backgroundScheduler.cancelAll()
                            }
                        }

                    VStack(alignment: .leading) {
                        HStack {
                            Text("置信度阈值")
                            Spacer()
                            Text(String(format: "%.2f", confidenceThreshold))
                                .foregroundStyle(AppTheme.primaryBlue)
                        }
                        Slider(value: $confidenceThreshold, in: 0.5...0.95)
                            .onChange(of: confidenceThreshold) { _, newValue in
                                saveSetting(SettingKeys.confidenceThreshold, value: String(newValue))
                            }
                    }
                    Text("低于此值将请求云端识别")
                        .font(.caption)
                        .foregroundStyle(AppTheme.secondaryText)
                }

                // 云端设置
                Section("云端") {
                    Toggle("启用云端 API", isOn: $cloudEnabled)
                        .onChange(of: cloudEnabled) { _, newValue in
                            saveSetting(SettingKeys.cloudEnabled, value: String(newValue))
                        }

                    VStack(alignment: .leading) {
                        HStack {
                            Text("日预算限额（元）")
                            Spacer()
                            Text(String(format: "%.0f", dailyBudget))
                                .foregroundStyle(AppTheme.primaryBlue)
                        }
                        Slider(value: $dailyBudget, in: 0...50, step: 1)
                            .onChange(of: dailyBudget) { _, newValue in
                                saveSetting(SettingKeys.dailyBudget, value: String(newValue))
                            }
                    }
                    Text("云端 API 每日消费上限")
                        .font(.caption)
                        .foregroundStyle(AppTheme.secondaryText)
                }

                // 数据同步
                Section("数据同步") {
                    Toggle("仅 WiFi 同步", isOn: $syncWifiOnly)
                        .onChange(of: syncWifiOnly) { _, newValue in
                            saveSetting(SettingKeys.syncWifiOnly, value: String(newValue))
                        }

                    Button {
                        triggerSync()
                    } label: {
                        HStack {
                            Image(systemName: "arrow.triangle.2.circlepath")
                            Text("立即同步")
                        }
                    }
                    .disabled(appState.syncState == .syncing)

                    if case .success(let msg) = appState.syncState {
                        Label(msg, systemImage: "checkmark.circle.fill")
                            .foregroundStyle(AppTheme.successGreen)
                            .font(.caption)
                    }
                    if case .error(let msg) = appState.syncState {
                        Label(msg, systemImage: "xmark.circle.fill")
                            .foregroundStyle(AppTheme.errorRed)
                            .font(.caption)
                    }
                }

                // 安全设置
                Section("安全") {
                    HStack {
                        Image(systemName: "lock.shield.fill")
                            .foregroundStyle(AppTheme.primaryBlue)
                        VStack(alignment: .leading) {
                            Text("Data Protection")
                            Text("NSFileProtectionComplete 已启用")
                                .font(.caption)
                                .foregroundStyle(AppTheme.secondaryText)
                        }
                    }

                    HStack {
                        Image(systemName: "key.fill")
                            .foregroundStyle(AppTheme.primaryBlue)
                        VStack(alignment: .leading) {
                            Text("Keychain 安全存储")
                            Text("Token、密钥已加密存储")
                                .font(.caption)
                                .foregroundStyle(AppTheme.secondaryText)
                        }
                    }
                }

                // 关于
                Section("关于") {
                    LabeledContent("版本", value: "1.0.0")
                    LabeledContent("模型版本", value: "MiniCPM-V 4.6")
                    LabeledContent("推理后端", value: "Core ML")
                }
            }
            .navigationTitle("设置")
            .onAppear { loadSettings() }
        }
    }

    // MARK: - Settings Persistence

    private func loadSettings() {
        let context = appState.coreDataStack.viewContext
        autoRecognition = UserSettingEntity.getBool(SettingKeys.autoRecognition, in: context)
        cloudEnabled = UserSettingEntity.getBool(SettingKeys.cloudEnabled, in: context)
        syncWifiOnly = UserSettingEntity.getBool(SettingKeys.syncWifiOnly, default: true, in: context)
        confidenceThreshold = Double(UserSettingEntity.getFloat(SettingKeys.confidenceThreshold, default: 0.7, in: context))
        dailyBudget = Double(UserSettingEntity.getFloat(SettingKeys.dailyBudget, default: 10, in: context))
    }

    private func saveSetting(_ key: String, value: String) {
        let context = appState.coreDataStack.viewContext
        UserSettingEntity.set(key, value: value, in: context)
        appState.coreDataStack.save()
    }

    private func triggerSync() {
        appState.syncState = .syncing
        Task {
            let result = await appState.syncManager.fullSync()
            await MainActor.run {
                appState.syncState = result
            }
        }
    }
}

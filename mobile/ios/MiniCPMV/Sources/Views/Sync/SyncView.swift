import SwiftUI

/**
 * 数据同步管理页面
 *
 * 功能:
 * - 同步状态展示（Idle/Syncing/Success/Error）
 * - 手动同步触发
 * - 上次同步时间
 * - iCloud 同步开关（预留）
 *
 * 对应 Android 端的 SyncScreen.kt
 */
struct SyncView: View {

    @EnvironmentObject var appState: AppState

    @State private var iCloudSyncEnabled = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // 状态图标
            switch appState.syncState {
            case .idle:
                SyncIconView(systemName: "arrow.triangle.2.circlepath", color: AppTheme.primaryBlue, title: "数据同步", subtitle: "将本地识别记录同步到云端")

            case .syncing:
                ProgressView()
                    .scaleEffect(1.5)
                    .padding(.bottom, 8)
                Text("同步中...")
                    .font(.title3)

            case .success(let message):
                SyncIconView(systemName: "checkmark.circle.fill", color: AppTheme.successGreen, title: "同步成功", subtitle: message)

            case .error(let message):
                SyncIconView(systemName: "xmark.circle.fill", color: AppTheme.errorRed, title: "同步失败", subtitle: message)
            }

            // 上次同步时间
            if let lastSync = getLastSyncTime() {
                Text("上次同步: \(lastSync)")
                    .font(.caption)
                    .foregroundStyle(AppTheme.secondaryText)
            }

            // 操作按钮
            if appState.syncState != .syncing {
                Button {
                    triggerSync()
                } label: {
                    Text(appState.syncState == .idle ? "开始同步" : "再次同步")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(AppTheme.primaryBlue, in: RoundedRectangle(cornerRadius: 12))
                        .foregroundStyle(.white)
                }
                .padding(.horizontal, 32)

                if case .error(_) = appState.syncState {
                    Button("重试") {
                        triggerSync()
                    }
                    .tint(AppTheme.primaryBlue)
                }
            }

            // iCloud 同步开关
            Toggle(isOn: $iCloudSyncEnabled) {
                Label("iCloud 同步", systemImage: "icloud")
            }
            .padding(.horizontal, 32)
            .padding(.top, 24)

            Spacer()
        }
        .navigationTitle("数据同步")
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

    private func getLastSyncTime() -> String? {
        let context = appState.coreDataStack.viewContext
        guard let isoString = UserSettingEntity.get(SettingKeys.lastSyncTime, in: context) else {
            return nil
        }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: isoString) else { return nil }

        let display = DateFormatter()
        display.dateStyle = .short
        display.timeStyle = .short
        return display.string(from: date)
    }
}

struct SyncIconView: View {
    let systemName: String
    let color: Color
    let title: String
    let subtitle: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: systemName)
                .font(.system(size: 64))
                .foregroundStyle(color)

            Text(title)
                .font(.title2.bold())

            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(AppTheme.secondaryText)
                .multilineTextAlignment(.center)
        }
    }
}

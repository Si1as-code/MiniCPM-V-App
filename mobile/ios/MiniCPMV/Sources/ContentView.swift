import SwiftUI

/**
 * 主界面 - TabView 三标签页导航
 *
 * 结构与 Android 端 BottomBar 对应：
 * - 拍照（Camera）
 * - 历史（History）
 * - 设置（Settings）
 */
struct ContentView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        TabView {
            CameraView()
                .tabItem {
                    Label("拍照", systemImage: "camera.fill")
                }
                .tag(0)

            HistoryView()
                .tabItem {
                    Label("历史", systemImage: "clock.arrow.circlepath")
                }
                .tag(1)

            SettingsView()
                .tabItem {
                    Label("设置", systemImage: "gearshape.fill")
                }
                .tag(2)
        }
        .tint(AppTheme.primaryBlue)
    }
}

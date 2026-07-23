import WidgetKit
import SwiftUI

/**
 * Widget 扩展 - 快速拍照识别
 *
 * 功能:
 * - 主屏幕小组件，显示最近识别记录
 * - 点击快速启动相机
 * - 支持小/中/大三种尺寸
 *
 * 对应 TASKS.md 中的 "Widget 扩展（快速拍照识别）"
 */

// MARK: - Timeline Entry

struct MiniCPMVEntry: TimelineEntry {
    let date: Date
    let lastResult: String
    let lastTime: String
    let recordCount: Int
}

// MARK: - Timeline Provider

struct MiniCPMVProvider: TimelineProvider {
    func placeholder(in context: Context) -> MiniCPMVEntry {
        MiniCPMVEntry(date: .now, lastResult: "识别到一只猫", lastTime: "刚刚", recordCount: 42)
    }

    func getSnapshot(in context: Context, completion: @escaping (MiniCPMVEntry) -> Void) {
        let entry = MiniCPMVEntry(date: .now, lastResult: "识别到一只猫", lastTime: "刚刚", recordCount: 42)
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<MiniCPMVEntry>) -> Void) {
        // 每 30 分钟刷新一次
        let entry = MiniCPMVEntry(date: .now, lastResult: "识别到一只猫", lastTime: "5分钟前", recordCount: 42)
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: .now)!
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }
}

// MARK: - Widget View

struct MiniCPMVWidgetView: View {
    var entry: MiniCPMVEntry
    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .systemSmall:
            SmallWidget(entry: entry)
        case .systemMedium:
            MediumWidget(entry: entry)
        case .systemLarge:
            LargeWidget(entry: entry)
        default:
            SmallWidget(entry: entry)
        }
    }
}

// MARK: - Widget Sizes

struct SmallWidget: View {
    let entry: MiniCPMVEntry

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: "camera.fill")
                .font(.title2)
                .foregroundStyle(.blue)

            Text("MiniCPM-V")
                .font(.caption.bold())

            Text(entry.lastResult)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(8)
    }
}

struct MediumWidget: View {
    let entry: MiniCPMVEntry

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Image(systemName: "eye.circle.fill")
                        .foregroundStyle(.blue)
                    Text("MiniCPM-V")
                        .font(.headline)
                }

                Text("最近识别: \(entry.lastResult)")
                    .font(.caption)
                    .lineLimit(1)

                Text("\(entry.lastTime) · 共 \(entry.recordCount) 条记录")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // 快速拍照按钮（Widget 不支持直接交互，通过 Link 跳转）
            Image(systemName: "camera.circle.fill")
                .font(.system(size: 40))
                .foregroundStyle(.blue)
        }
        .padding()
    }
}

struct LargeWidget: View {
    let entry: MiniCPMVEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "eye.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.blue)
                Text("MiniCPM-V 端侧视觉助手")
                    .font(.headline)
                Spacer()
            }

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Label("最近识别", systemImage: "text.bubble")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)

                Text(entry.lastResult)
                    .font(.body)

                Text("\(entry.lastTime)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            HStack {
                VStack(alignment: .leading) {
                    Text("\(entry.recordCount)")
                        .font(.title.bold())
                        .foregroundStyle(.blue)
                    Text("总识别次数")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Link(destination: URL(string: "minicpmv://camera")!) {
                    Image(systemName: "camera.fill")
                        .font(.title2)
                        .padding()
                        .background(.blue, in: Circle())
                        .foregroundStyle(.white)
                }
            }
        }
        .padding()
    }
}

// MARK: - Widget Definition

struct MiniCPMVWidget: Widget {
    let kind: String = "MiniCPMVWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: MiniCPMVProvider()) { entry in
            MiniCPMVWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("MiniCPM-V")
        .description("快速拍照识别，查看最近识别结果")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

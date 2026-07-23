import SwiftUI
import CoreData

/**
 * 历史记录页面
 *
 * 功能:
 * - 搜索栏（实时过滤）
 * - 记录列表（LazyVStack）
 * - 同步状态标记
 * - 删除记录
 *
 * 对应 Android 端的 HistoryScreen.kt
 */
struct HistoryView: View {

    @EnvironmentObject var appState: AppState
    @State private var searchText = ""
    @State private var records: [RecognitionRecordEntity] = []

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // 搜索栏
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(AppTheme.secondaryText)
                    TextField("搜索识别记录...", text: $searchText)
                        .textFieldStyle(.plain)
                        .onChange(of: searchText) { _, _ in
                            fetchRecords()
                        }
                }
                .padding(12)
                .background(AppTheme.surfaceVariant, in: RoundedRectangle(cornerRadius: 24))
                .padding()

                // 记录数量
                Text("共 \(records.count) 条记录")
                    .font(.caption)
                    .foregroundStyle(AppTheme.secondaryText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)

                // 记录列表
                if records.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "photo.on.rectangle.angled")
                            .font(.system(size: 48))
                            .foregroundStyle(AppTheme.secondaryText)
                        Text("暂无识别记录")
                            .foregroundStyle(AppTheme.secondaryText)
                    }
                    .frame(maxHeight: .infinity)
                } else {
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(records, id: \.id) { record in
                                HistoryItemCard(record: record) {
                                    deleteRecord(record)
                                }
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("历史记录")
            .onAppear { fetchRecords() }
        }
    }

    // MARK: - Data

    private func fetchRecords() {
        let context = appState.coreDataStack.viewContext
        let request: NSFetchRequest<RecognitionRecordEntity> = NSFetchRequest(entityName: "RecognitionRecordEntity")
        request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: false)]

        if !searchText.isEmpty {
            request.predicate = NSPredicate(
                format: "answer CONTAINS[cd] %@ OR question CONTAINS[cd] %@",
                searchText, searchText
            )
        }

        records = (try? context.fetch(request)) ?? []
    }

    private func deleteRecord(_ record: RecognitionRecordEntity) {
        let context = appState.coreDataStack.viewContext
        context.delete(record)
        appState.coreDataStack.save()
        fetchRecords()
    }
}

// MARK: - History Item Card

struct HistoryItemCard: View {
    let record: RecognitionRecordEntity
    let onDelete: () -> Void

    private let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(record.question ?? "")
                    .font(.subheadline.weight(.medium))
                    .lineLimit(1)

                Spacer()

                if !record.synced {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.caption)
                        .foregroundStyle(AppTheme.primaryBlue)
                }
            }

            Text(record.answer ?? "")
                .font(.caption)
                .foregroundStyle(AppTheme.secondaryText)
                .lineLimit(2)

            HStack {
                Text(dateFormatter.string(from: record.createdAt ?? Date()))
                    .font(.caption2)
                    .foregroundStyle(AppTheme.secondaryText)

                Spacer()

                Text(record.taskType ?? "local")
                    .font(.caption2.weight(.medium))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(AppTheme.surfaceVariant, in: Capsule())

                Button(role: .destructive, action: onDelete) {
                    Image(systemName: "trash")
                        .font(.caption)
                }
            }
        }
        .padding()
        .background(AppTheme.surfaceVariant.opacity(0.5), in: RoundedRectangle(cornerRadius: AppTheme.cornerRadius))
    }
}

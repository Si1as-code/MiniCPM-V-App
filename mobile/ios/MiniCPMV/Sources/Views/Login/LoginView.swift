import SwiftUI

/**
 * 登录/注册页面
 *
 * 功能:
 * - 手机号 + 验证码登录
 * - Sign in with Apple
 * - 输入验证
 *
 * 对应 Android 端的 LoginScreen.kt
 */
struct LoginView: View {

    @EnvironmentObject var appState: AppState
    @State private var phone = ""
    @State private var code = ""
    @State private var isCodeSent = false
    @State private var isLoading = false
    @State private var errorMessage: String? = nil

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Logo
            VStack(spacing: 8) {
                Image(systemName: "eye.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(AppTheme.primaryBlue)

                Text("MiniCPM-V")
                    .font(.largeTitle.bold())
                    .foregroundStyle(AppTheme.primaryBlue)

                Text("端侧视觉助手")
                    .font(.body)
                    .foregroundStyle(AppTheme.secondaryText)
            }

            Spacer()

            // 手机号输入
            VStack(spacing: 16) {
                HStack {
                    Image(systemName: "phone")
                        .foregroundStyle(AppTheme.secondaryText)
                    TextField("手机号", text: $phone)
                        .textFieldStyle(.plain)
                        .keyboardType(.phonePad)
                        .onChange(of: phone) { _, newValue in
                            phone = newValue.filter { $0.isNumber }.prefix(11).description
                        }
                }
                .padding()
                .background(AppTheme.surfaceVariant, in: RoundedRectangle(cornerRadius: 12))

                HStack {
                    HStack {
                        Image(systemName: "shield.lefthalf.filled")
                            .foregroundStyle(AppTheme.secondaryText)
                        TextField("验证码", text: $code)
                            .textFieldStyle(.plain)
                            .keyboardType(.numberPad)
                            .onChange(of: code) { _, newValue in
                                code = newValue.filter { $0.isNumber }.prefix(6).description
                            }
                    }
                    .padding()
                    .background(AppTheme.surfaceVariant, in: RoundedRectangle(cornerRadius: 12))

                    Button(isCodeSent ? "已发送" : "获取验证码") {
                        isCodeSent = true
                    }
                    .disabled(phone.count != 11 || isCodeSent)
                    .buttonStyle(.bordered)
                    .tint(AppTheme.primaryBlue)
                }
            }

            // 错误信息
            if let error = errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(AppTheme.errorRed)
            }

            // 登录按钮
            Button {
                login()
            } label: {
                HStack {
                    if isLoading {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Text("登录 / 注册")
                            .fontWeight(.semibold)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(phone.count == 11 && code.count == 6 ? AppTheme.primaryBlue : AppTheme.surfaceVariant, in: RoundedRectangle(cornerRadius: 12))
                .foregroundStyle(.white)
            }
            .disabled(phone.count != 11 || code.count != 6 || isLoading)

            // Sign in with Apple（预留）
            Button {
                // TODO: 调用 AuthenticationServices
            } label: {
                HStack {
                    Image(systemName: "applelogo")
                    Text("Sign in with Apple")
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(.black, in: RoundedRectangle(cornerRadius: 12))
                .foregroundStyle(.white)
            }

            Spacer()
        }
        .padding(.horizontal, 32)
    }

    private func login() {
        isLoading = true
        errorMessage = nil

        Task {
            // TODO: 调用后端登录 API
            try? await Task.sleep(nanoseconds: 1_000_000_000)

            await MainActor.run {
                isLoading = false
                // 模拟登录成功，保存 Token 到 Keychain
                appState.keychainManager.save(.accessToken, value: "mock_token_\(UUID().uuidString)")
                appState.keychainManager.save(.userId, value: phone)
                appState.isAuthenticated = true
                appState.currentUser = User(id: phone, token: "mock_token")
            }
        }
    }
}

/**
 * 对话页面
 */
struct ChatView: View {
    let recordId: UUID

    @EnvironmentObject var appState: AppState
    @State private var messages: [ConversationEntity] = []
    @State private var inputText = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(messages, id: \.id) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _, _ in
                    if let lastId = messages.last?.id {
                        withAnimation { proxy.scrollTo(lastId, anchor: .bottom) }
                    }
                }
            }

            // 输入栏
            HStack {
                TextField("输入问题...", text: $inputText, axis: .vertical)
                    .textFieldStyle(.plain)
                    .padding(10)
                    .background(AppTheme.surfaceVariant, in: RoundedRectangle(cornerRadius: 20))
                    .lineLimit(3)

                Button {
                    sendMessage()
                } label: {
                    Image(systemName: "paperplane.fill")
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(AppTheme.primaryBlue, in: Circle())
                }
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            .padding()
        }
        .navigationTitle("对话")
        .onAppear { fetchMessages() }
    }

    private func fetchMessages() {
        let context = appState.coreDataStack.viewContext
        let request: NSFetchRequest<ConversationEntity> = NSFetchRequest(entityName: "ConversationEntity")
        request.predicate = NSPredicate(format: "recordId == %@", recordId as CVarArg)
        request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: true)]
        messages = (try? context.fetch(request)) ?? []
    }

    private func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }

        let context = appState.coreDataStack.viewContext
        ConversationEntity.create(in: context, recordId: recordId, role: "user", content: text)
        appState.coreDataStack.save()

        // 模拟助手回复
        ConversationEntity.create(in: context, recordId: recordId, role: "assistant", content: "[自动回复] 基于上下文的回答...")
        appState.coreDataStack.save()

        inputText = ""
        fetchMessages()
    }
}

struct MessageBubble: View {
    let message: ConversationEntity

    var body: some View {
        let isUser = message.role == "user"

        HStack {
            if isUser { Spacer() }

            Text(message.content ?? "")
                .padding(12)
                .background(
                    isUser ? AppTheme.primaryBlue : AppTheme.surfaceVariant,
                    in: RoundedRectangle(cornerRadius: 16)
                )
                .foregroundStyle(isUser ? .white : AppTheme.primaryText)
                .frame(maxWidth: 260, alignment: isUser ? .trailing : .leading)

            if !isUser { Spacer() }
        }
    }
}

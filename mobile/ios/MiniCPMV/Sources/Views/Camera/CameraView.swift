import SwiftUI
import AVFoundation

/**
 * 相机拍照页面
 *
 * 功能:
 * - AVFoundation 实时预览（UIViewRepresentable 包装 AVCaptureVideoPreviewLayer）
 * - 拍照按钮
 * - 闪光灯切换
 * - 前后摄像头切换
 * - 识别结果展示
 * - 加载指示器
 *
 * 对应 Android 端的 CameraScreen.kt
 */
struct CameraView: View {

    @EnvironmentObject var appState: AppState
    @StateObject private var cameraManager = CameraManager()
    @State private var showResult = false

    var body: some View {
        ZStack {
            // 相机预览
            CameraPreviewLayer(session: cameraManager.session)
                .ignoresSafeArea()

            // 顶部控制栏
            VStack {
                HStack {
                    // 闪光灯按钮
                    Button(action: toggleFlash) {
                        Image(systemName: flashIcon)
                            .font(.title2)
                            .foregroundStyle(.white)
                            .padding(12)
                            .background(.black.opacity(0.4), in: Circle())
                    }

                    Spacer()

                    // 切换摄像头
                    Button(action: cameraManager.switchCamera) {
                        Image(systemName: "camera.rotate")
                            .font(.title2)
                            .foregroundStyle(.white)
                            .padding(12)
                            .background(.black.opacity(0.4), in: Circle())
                    }
                }
                .padding()

                Spacer()
            }

            // 底部控制区
            VStack {
                Spacer()

                // 识别结果卡片
                if let result = appState.lastResult, !appState.isInferencing {
                    ResultCardView(result: result)
                        .padding(.horizontal)
                        .padding(.bottom, 8)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // 拍照按钮
                Button(action: capturePhoto) {
                    ZStack {
                        Circle()
                            .fill(appState.isInferencing ? AppTheme.surfaceVariant : AppTheme.primaryBlue)
                            .frame(width: 76, height: 76)

                        if appState.isInferencing {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: "camera.fill")
                                .font(.title)
                                .foregroundStyle(.white)
                        }
                    }
                }
                .disabled(appState.isInferencing)
                .padding(.bottom, 32)
            }

            // 加载遮罩
            if appState.isInferencing {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
            }
        }
        .onAppear {
            cameraManager.configureSession()
            cameraManager.startSession()
        }
        .onDisappear {
            cameraManager.stopSession()
        }
        .animation(.easeInOut(duration: 0.3), value: appState.isInferencing)
    }

    // MARK: - Actions

    private func capturePhoto() {
        cameraManager.capturePhoto()

        // 监听拍照结果
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if let image = cameraManager.capturedImage {
                Task {
                    await runInference(image: image)
                }
            }
        }
    }

    private func runInference(image: UIImage) async {
        await MainActor.run {
            appState.isInferencing = true
        }

        let result = await appState.inferenceEngine.inference(image: image)

        await MainActor.run {
            appState.lastResult = result
            appState.isInferencing = false

            // 保存到 Core Data
            saveResult(result)
        }
    }

    private func saveResult(_ result: InferenceResult) {
        let context = appState.coreDataStack.viewContext
        let record = RecognitionRecordEntity.create(
            in: context,
            imageHash: UUID().uuidString,
            imagePath: "",
            question: "描述这张图片",
            answer: result.answer,
            confidence: result.confidence
        )
        appState.coreDataStack.save()

        // 保存对话
        ConversationEntity.create(in: context, recordId: record.id, role: "user", content: "描述这张图片")
        ConversationEntity.create(in: context, recordId: record.id, role: "assistant", content: result.answer)
        appState.coreDataStack.save()
    }

    private func toggleFlash() {
        switch cameraManager.flashMode {
        case .auto: cameraManager.flashMode = .on
        case .on: cameraManager.flashMode = .off
        case .off: cameraManager.flashMode = .auto
        @unknown default: break
        }
    }

    private var flashIcon: String {
        switch cameraManager.flashMode {
        case .auto: return "bolt.badge.a"
        case .on: return "bolt.fill"
        case .off: return "bolt.slash.fill"
        @unknown default: return "bolt.badge.a"
        }
    }
}

// MARK: - Camera Preview Layer

/**
 * UIViewRepresentable 包装 AVCaptureVideoPreviewLayer
 */
struct CameraPreviewLayer: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.videoPreviewLayer.session = session
        view.videoPreviewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}

    static func dismantleUIView(_ uiView: PreviewView, coordinator: ()) {
        uiView.videoPreviewLayer.session = nil
    }
}

final class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var videoPreviewLayer: AVCaptureVideoPreviewLayer {
        layer as! AVCaptureVideoPreviewLayer
    }
}

// MARK: - Result Card

struct ResultCardView: View {
    let result: InferenceResult

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(result.success ? "识别成功" : "识别失败")
                    .font(.headline)
                    .foregroundStyle(result.success ? AppTheme.successGreen : AppTheme.errorRed)

                Spacer()

                Text(String(format: "%.0fms", result.latencyMs))
                    .font(.caption)
                    .foregroundStyle(AppTheme.secondaryText)
            }

            Text(result.answer)
                .font(.subheadline)
                .foregroundStyle(AppTheme.primaryText)
                .lineLimit(3)

            if result.success {
                HStack {
                    ProgressView(value: Double(result.confidence))
                        .tint(result.confidence > 0.8 ? AppTheme.successGreen : AppTheme.primaryBlue)

                    Text(String(format: "%.0f%%", result.confidence * 100))
                        .font(.captionBold)
                        .foregroundStyle(AppTheme.primaryText)
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: AppTheme.cornerRadius))
    }
}

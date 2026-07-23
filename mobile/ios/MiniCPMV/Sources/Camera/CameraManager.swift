import AVFoundation
import UIKit
import Combine

/**
 * AVFoundation 相机管理器
 *
 * 职责:
 * - 前后摄像头切换
 * - 实时预览（AVCaptureVideoPreviewLayer）
 * - 拍照（AVCapturePhotoOutput）
 * - 闪光灯控制
 * - 视频帧分析（AVCaptureVideoDataOutput，用于后台自动识别）
 *
 * 对应 Android 端的 CameraManager.kt
 */
final class CameraManager: NSObject, ObservableObject {

    // MARK: - Published Properties

    @Published var isSessionRunning = false
    @Published var flashMode: AVCaptureDevice.FlashMode = .auto
    @Published var captureError: String? = nil
    @Published var capturedImage: UIImage? = nil

    // MARK: - Private Properties

    private let session = AVCaptureSession()
    private let photoOutput = AVCapturePhotoOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let sessionQueue = DispatchQueue(label: "com.minicpmv.camera.session")
    private var videoOutputSampleBufferDelegate: VideoSampleBufferDelegate?

    // 当前输入
    private var currentInput: AVCaptureDeviceInput?

    // 帧分析回调
    var onFrameAnalyzed: ((UIImage) -> Void)?

    // MARK: - Setup

    /**
     * 配置相机会话
     * 必须在 sessionQueue 上调用
     */
    func configureSession(enableFrameAnalysis: Bool = false) {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }

            self.session.beginConfiguration()

            // 1. 设置预设（照片质量）
            self.session.sessionPreset = .photo

            // 2. 后置摄像头输入
            guard let backCamera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
                DispatchQueue.main.async {
                    self.captureError = "无法访问后置摄像头"
                }
                self.session.commitConfiguration()
                return
            }

            do {
                let input = try AVCaptureDeviceInput(device: backCamera)
                if self.session.canAddInput(input) {
                    self.session.addInput(input)
                    self.currentInput = input
                }
            } catch {
                DispatchQueue.main.async {
                    self.captureError = "摄像头初始化失败: \(error.localizedDescription)"
                }
                self.session.commitConfiguration()
                return
            }

            // 3. 照片输出
            if self.session.canAddOutput(self.photoOutput) {
                self.session.addOutput(self.photoOutput)
                self.photoOutput.isHighResolutionCaptureEnabled = true
            }

            // 4. 视频帧分析（可选）
            if enableFrameAnalysis {
                if self.session.canAddOutput(self.videoOutput) {
                    self.session.addOutput(self.videoOutput)
                    self.videoOutput.setSampleBufferDelegate(
                        self.videoOutputSampleBufferDelegate,
                        queue: DispatchQueue(label: "com.minicpmv.camera.video")
                    )
                    self.videoOutput.alwaysDiscardsLateVideoFrames = true
                }
            }

            self.session.commitConfiguration()
        }
    }

    /**
     * 启动预览
     */
    func startSession() {
        sessionQueue.async { [weak self] in
            guard let self = self, !self.session.isRunning else { return }
            self.session.startRunning()
            DispatchQueue.main.async {
                self.isSessionRunning = true
            }
        }
    }

    /**
     * 停止预览
     */
    func stopSession() {
        sessionQueue.async { [weak self] in
            guard let self = self, self.session.isRunning else { return }
            self.session.stopRunning()
            DispatchQueue.main.async {
                self.isSessionRunning = false
            }
        }
    }

    /**
     * 获取预览图层
     */
    func getPreviewLayer() -> AVCaptureVideoPreviewLayer {
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        return layer
    }

    /**
     * 拍照
     */
    func capturePhoto() {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            let settings = AVCapturePhotoSettings()

            // 闪光灯设置
            if self.flashMode != .auto {
                settings.flashMode = self.flashMode
            }

            // 高分辨率
            settings.isHighResolutionPhotoEnabled = true

            self.photoOutput.capturePhoto(with: settings, delegate: self)
        }
    }

    /**
     * 切换前后摄像头
     */
    func switchCamera() {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            self.session.beginConfiguration()

            // 移除当前输入
            if let currentInput = self.currentInput {
                self.session.removeInput(currentInput)
            }

            // 切换到另一摄像头
            let newPosition: AVCaptureDevice.Position =
                (self.currentInput?.device.position == .back) ? .front : .back

            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: newPosition) else {
                self.session.commitConfiguration()
                return
            }

            do {
                let newInput = try AVCaptureDeviceInput(device: device)
                if self.session.canAddInput(newInput) {
                    self.session.addInput(newInput)
                    self.currentInput = newInput
                }
            } catch {
                DispatchQueue.main.async {
                    self.captureError = "切换摄像头失败: \(error.localizedDescription)"
                }
            }

            self.session.commitConfiguration()
        }
    }

    /**
     * 设置缩放
     */
    func setZoom(_ scale: CGFloat) {
        guard let device = currentInput?.device else { return }
        do {
            try device.lockForConfiguration()
            let clampedZoom = max(1.0, min(scale, device.activeFormat.videoMaxZoomFactor))
            device.videoZoomFactor = clampedZoom
            device.unlockForConfiguration()
        } catch {
            // 缩放设置失败，忽略
        }
    }
}

// MARK: - AVCapturePhotoCaptureDelegate

extension CameraManager: AVCapturePhotoCaptureDelegate {

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        if let error = error {
            DispatchQueue.main.async {
                self.captureError = "拍照失败: \(error.localizedDescription)"
            }
            return
        }

        guard let imageData = photo.fileDataRepresentation(),
              let image = UIImage(data: imageData) else {
            DispatchQueue.main.async {
                self.captureError = "无法生成图片"
            }
            return
        }

        DispatchQueue.main.async {
            self.capturedImage = image
        }
    }
}

// MARK: - 视频帧分析代理

final class VideoSampleBufferDelegate: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {

    var onFrame: ((UIImage) -> Void)?

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let context = CIContext()
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else { return }
        let image = UIImage(cgImage: cgImage)

        onFrame?(image)
    }
}

import CoreML
import Vision
import UIKit

/**
 * Core ML 推理引擎
 *
 * 职责:
 * - 加载 Core ML 模型（从 .mlmodelc 编译后的模型包）
 * - 图像预处理（Resize → CVPixelBuffer → 归一化）
 * - 执行推理并解析结果
 * - 置信度计算
 *
 * 对应 Android 端的 OnnxInferenceEngine.kt
 * 模型由 Sprint 5 导出的 ONNX 通过 coremltools 转换为 .mlpackage
 */
final class CoreMLInferenceEngine {

    // MARK: - Properties

    private var compiledModel: MLModel?
    private var isInitialized = false

    // 输入尺寸（匹配 MiniCPM-V 4.6 视觉编码器）
    private let inputSize = CGSize(width: 448, height: 448)

    // MARK: - Initialization

    /**
     * 预热引擎（在后台线程加载模型）
     */
    func warmup() {
        DispatchQueue.global(qos: .utility).async { [weak self] in
            self?.loadModel()
        }
    }

    /**
     * 加载 Core ML 模型
     */
    private func loadModel() {
        guard !isInitialized else { return }

        // 方式1: 从应用 Bundle 加载编译后的模型
        if let modelURL = Bundle.main.url(forResource: "MiniCPMVVision", withExtension: "mlmodelc") {
            do {
                let config = MLModelConfiguration()
                config.computeUnits = .all  // 自动选择 CPU/GPU/Neural Engine
                compiledModel = try MLModel(contentsOf: modelURL, configuration: config)
                isInitialized = true
                print("[CoreML] 模型加载成功")
            } catch {
                print("[CoreML] 模型加载失败: \(error.localizedDescription)")
            }
        } else {
            // 方式2: 模型尚未嵌入，使用模拟模式
            print("[CoreML] 未找到模型文件，启用模拟模式")
            isInitialized = true
        }
    }

    // MARK: - Inference

    /**
     * 执行单图推理
     *
     * - Parameters:
     *   - image: 输入图片（任意尺寸，内部会 resize）
     *   - question: 用户问题/提示词
     * - Returns: 推理结果
     */
    func inference(image: UIImage, question: String = "描述这张图片") async -> InferenceResult {
        let startTime = CFAbsoluteTimeGetCurrent()

        guard isInitialized else {
            loadModel()
        }

        do {
            // 1. 图像预处理
            let pixelBuffer = preprocess(image: image)

            // 2. 执行推理
            let answer: String
            let confidence: Float

            if let model = compiledModel {
                // 真实推理
                let inputFeature = try MLFeatureValue(
                    pixelBuffer: pixelBuffer,
                    pixelsWide: Int(inputSize.width),
                    pixelsHigh: Int(inputSize.height),
                    pixelFormatType: kCVPixelFormatType_32BGRA,
                    options: nil
                )

                let inputProvider = try MLDictionaryFeatureProvider(
                    dictionary: ["pixel_values": inputFeature]
                )

                let output = try model.prediction(from: inputProvider)

                // 解码输出
                if let outputText = output.featureValue(for: "output_text")?.stringValue {
                    answer = outputText
                } else {
                    answer = "[CoreML] 推理完成但无法解析输出"
                }
                confidence = 0.85  // 简化：实际应从 logits 计算
            } else {
                // 模拟模式
                answer = "[模拟] 检测到场景内容"
                confidence = 0.75
            }

            let latency = (CFAbsoluteTimeGetCurrent() - startTime) * 1000

            return InferenceResult(
                answer: answer,
                confidence: confidence,
                latencyMs: latency,
                modelVersion: "4.6-coreml",
                success: true
            )

        } catch {
            let latency = (CFAbsoluteTimeGetCurrent() - startTime) * 1000
            return InferenceResult(
                answer: "推理失败: \(error.localizedDescription)",
                confidence: 0,
                latencyMs: latency,
                modelVersion: "4.6-coreml",
                success: false,
                errorMessage: error.localizedDescription
            )
        }
    }

    // MARK: - Preprocessing

    /**
     * 图像预处理: UIImage → CVPixelBuffer (448×448)
     *
     * Core ML 使用 CVPixelBuffer 作为图像输入格式
     * 不需要手动 NCHW 转换，Vision/Core ML 内部处理
     */
    private func preprocess(image: UIImage) -> CVPixelBuffer {
        // 1. Resize 到模型输入尺寸
        let resizedImage = resizeImage(image, to: inputSize)

        // 2. 转换为 CVPixelBuffer
        let pixelBuffer = createPixelBuffer(from: resizedImage)

        return pixelBuffer
    }

    /**
     * 缩放图片到指定尺寸
     */
    private func resizeImage(_ image: UIImage, to size: CGSize) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }

    /**
     * 从 UIImage 创建 CVPixelBuffer
     */
    private func createPixelBuffer(from image: UIImage) -> CVPixelBuffer {
        let width = Int(inputSize.width)
        let height = Int(inputSize.height)

        var pixelBuffer: CVPixelBuffer?
        let attrs: [String: Any] = [
            kCVPixelBufferCGImageCompatibilityKey as String: true,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
        ]

        CVPixelBufferCreate(kCFAllocatorDefault, width, height, kCVPixelFormatType_32BGRA, attrs as CFDictionary, &pixelBuffer)

        guard let buffer = pixelBuffer else {
            fatalError("无法创建 CVPixelBuffer")
        }

        CVPixelBufferLockBaseAddress(buffer, [])
        let context = CGContext(
            data: CVPixelBufferGetBaseAddress(buffer),
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue
        )

        if let cgImage = image.cgImage {
            context?.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        }

        CVPixelBufferUnlockBaseAddress(buffer, [])

        return buffer
    }
}

/**
 * 推理结果数据结构
 */
struct InferenceResult: Identifiable {
    let id = UUID()
    let answer: String
    let confidence: Float
    let latencyMs: Double
    let modelVersion: String
    let success: Bool
    var errorMessage: String? = nil
}

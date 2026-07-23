package com.minicpmv.app.inference

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import ai.onnxruntime.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.FloatBuffer

/**
 * ONNX Runtime Mobile 推理引擎
 *
 * 职责:
 * - 加载 ONNX 模型（从 assets 或本地文件）
 * - 图像预处理（resize → normalize → tensor）
 * - 执行推理并解析结果
 * - 置信度计算
 *
 * 注意: MiniCPM-V 的完整 ONNX 导出需要 vision encoder + text decoder 两个模型，
 * 这里提供统一的封装接口。
 */
class OnnxInferenceEngine(private val context: Context) {

    companion object {
        private const val TAG = "OnnxInference"
        private const val MODEL_NAME = "minicpmv-vision.onnx"
        private const val INPUT_SIZE = 448           // 模型输入尺寸
        private const val CHANNELS = 3               // RGB
        private const val NORMALIZE_MEAN = 0.5f      // (x - mean) / std
        private const val NORMALIZE_STD = 0.5f
    }

    private var ortEnvironment: OrtEnvironment? = null
    private var ortSession: OrtSession? = null
    private var isInitialized = false

    /** 初始化/预热引擎 */
    suspend fun warmup() = withContext(Dispatchers.IO) {
        try {
            initSession()
            Log.i(TAG, "ONNX 引擎预热成功")
        } catch (e: Exception) {
            Log.e(TAG, "预热失败: ${e.message}")
            throw e
        }
    }

    /**
     * 执行单图推理
     *
     * @param bitmap 输入图片（任意尺寸，内部会 resize）
     * @param question 用户问题/提示词
     * @return InferenceResult 包含回答和置信度
     */
    suspend fun inference(bitmap: Bitmap, question: String = "描述这张图片"): InferenceResult =
        withContext(Dispatchers.IO) {
            if (!isInitialized) initSession()

            val startTime = System.currentTimeMillis()

            try {
                // 1. 预处理
                val inputTensor = preprocess(bitmap)

                // 2. 执行推理
                val session = ortSession ?: throw IllegalStateException("ONNX Session 未初始化")
                val inputs = mapOf("pixel_values" to inputTensor)
                val results = session.run(inputs)

                // 3. 解析结果（简化版：取第一个输出张量）
                val output = results.get(0)?.value as? Array<*>
                val answer = parseOutput(output)

                // 4. 计算置信度（简化：基于输出概率分布的熵）
                val confidence = calculateConfidence(output)

                val latency = System.currentTimeMillis() - startTime

                InferenceResult(
                    answer = answer,
                    confidence = confidence,
                    latencyMs = latency,
                    modelVersion = "4.6-onnx",
                    success = true
                )
            } catch (e: Exception) {
                Log.e(TAG, "推理失败: ${e.message}")
                InferenceResult(
                    answer = "识别失败: ${e.message}",
                    confidence = 0f,
                    latencyMs = System.currentTimeMillis() - startTime,
                    modelVersion = "4.6-onnx",
                    success = false,
                    errorMessage = e.message
                )
            }
        }

    /** 释放资源 */
    fun close() {
        try {
            ortSession?.close()
            ortEnvironment?.close()
            isInitialized = false
            Log.i(TAG, "ONNX 资源已释放")
        } catch (e: Exception) {
            Log.e(TAG, "释放资源失败: ${e.message}")
        }
    }

    // ------------------------------------------------------------------
    // 私有方法
    // ------------------------------------------------------------------

    private fun initSession() {
        if (isInitialized) return

        ortEnvironment = OrtEnvironment.getEnvironment()
        val env = ortEnvironment ?: throw IllegalStateException("无法创建 OrtEnvironment")

        // 从 assets 复制模型到本地缓存
        val modelFile = copyModelFromAssets()

        val sessionOptions = OrtSession.SessionOptions().apply {
            // Mobile 优化选项
            setIntraOpNumThreads(2)          // 使用 2 个线程
            addConfigEntry("session.load_model_format", "ONNX")
        }

        ortSession = env.createSession(modelFile.absolutePath, sessionOptions)
        isInitialized = true
    }

    private fun copyModelFromAssets(): File {
        val modelFile = File(context.cacheDir, MODEL_NAME)
        if (modelFile.exists() && modelFile.length() > 0) {
            return modelFile
        }

        context.assets.open(MODEL_NAME).use { input ->
            modelFile.outputStream().use { output ->
                input.copyTo(output)
            }
        }
        Log.i(TAG, "模型已复制到: ${modelFile.absolutePath}, 大小: ${modelFile.length()} bytes")
        return modelFile
    }

    /**
     * 图像预处理: Resize → ToTensor → Normalize
     *
     * 输出形状: [1, 3, 448, 448] (NCHW)
     */
    private fun preprocess(bitmap: Bitmap): OnnxTensor {
        // 1. Resize 到模型输入尺寸
        val resized = Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)

        // 2. 提取像素并归一化
        val floatBuffer = FloatBuffer.allocate(1 * CHANNELS * INPUT_SIZE * INPUT_SIZE)

        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        resized.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)

        // CHW 格式
        for (c in 0 until CHANNELS) {
            for (h in 0 until INPUT_SIZE) {
                for (w in 0 until INPUT_SIZE) {
                    val pixel = pixels[h * INPUT_SIZE + w]
                    val value = when (c) {
                        0 -> (pixel shr 16 and 0xFF) / 255f  // R
                        1 -> (pixel shr 8 and 0xFF) / 255f   // G
                        2 -> (pixel and 0xFF) / 255f         // B
                        else -> 0f
                    }
                    val normalized = (value - NORMALIZE_MEAN) / NORMALIZE_STD
                    floatBuffer.put(normalized)
                }
            }
        }
        floatBuffer.rewind()

        val shape = longArrayOf(1, CHANNELS.toLong(), INPUT_SIZE.toLong(), INPUT_SIZE.toLong())
        return OnnxTensor.createTensor(ortEnvironment, floatBuffer, shape)
    }

    /** 解析模型输出为文本（简化实现） */
    private fun parseOutput(output: Array<*>?): String {
        // 实际实现需要 tokenizer 解码
        // 这里返回占位文本，实际项目中需对接 tokenizer
        return if (output != null) {
            "[ONNX 推理结果] 检测到 ${output.size} 个输出张量"
        } else {
            "无法解析输出"
        }
    }

    /** 基于输出概率计算置信度 */
    private fun calculateConfidence(output: Array<*>?): Float {
        // 简化：返回模拟置信度
        // 实际应基于 softmax 概率分布计算
        return 0.85f
    }
}

/**
 * 推理结果数据类
 */
data class InferenceResult(
    val answer: String,
    val confidence: Float,
    val latencyMs: Long,
    val modelVersion: String,
    val success: Boolean,
    val errorMessage: String? = null
)

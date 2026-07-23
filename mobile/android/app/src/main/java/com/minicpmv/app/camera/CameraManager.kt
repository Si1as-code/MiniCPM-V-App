package com.minicpmv.app.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.util.Log
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * CameraX 相机管理器
 *
 * 职责:
 * - 预览流绑定
 * - 拍照（ImageCapture）
 * - 实时帧分析（ImageAnalysis）用于后台自动识别
 * - 权限状态管理
 */
class CameraManager(private val context: Context) {

    companion object {
        private const val TAG = "CameraManager"
    }

    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private var imageCapture: ImageCapture? = null
    private var imageAnalysis: ImageAnalysis? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: Camera? = null

    /** 帧分析结果通道 */
    private val frameChannel = Channel<Bitmap>(Channel.CONFLATED)

    /**
     * 启动相机预览
     *
     * @param previewView 预览视图
     * @param lifecycleOwner 生命周期持有者
     * @param onFrame 可选：实时帧回调（用于后台识别）
     */
    @Suppress("MissingPermission")
    suspend fun startCamera(
        previewView: PreviewView,
        lifecycleOwner: LifecycleOwner,
        enableAnalysis: Boolean = false,
        onFrame: ((Bitmap) -> Unit)? = null
    ) = withContext(Dispatchers.Main) {
        val provider = ProcessCameraProvider.getInstance(context).await()
        cameraProvider = provider

        val preview = Preview.Builder()
            .setTargetAspectRatio(AspectRatio.RATIO_4_3)
            .build()
            .also { it.surfaceProvider = previewView.surfaceProvider }

        imageCapture = ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
            .setTargetAspectRatio(AspectRatio.RATIO_4_3)
            .build()

        // 实时帧分析（可选）
        if (enableAnalysis && onFrame != null) {
            imageAnalysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setTargetAspectRatio(AspectRatio.RATIO_4_3)
                .build()
                .also { analysis ->
                    analysis.setAnalyzer(cameraExecutor) { imageProxy ->
                        val bitmap = imageProxy.toBitmap()
                        if (bitmap != null) {
                            onFrame(bitmap)
                        }
                        imageProxy.close()
                    }
                }
        }

        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

        try {
            provider.unbindAll()
            camera = provider.bindToLifecycle(
                lifecycleOwner,
                cameraSelector,
                preview,
                imageCapture,
                imageAnalysis
            )
            Log.i(TAG, "相机启动成功")
        } catch (e: Exception) {
            Log.e(TAG, "相机绑定失败: ${e.message}")
            throw e
        }
    }

    /** 拍照并返回 Bitmap */
    suspend fun takePhoto(): Bitmap = suspendCancellableCoroutine { continuation ->
        val capture = imageCapture ?: run {
            continuation.resumeWith(Result.failure(IllegalStateException("ImageCapture 未初始化")))
            return@suspendCancellableCoroutine
        }

        capture.takePicture(
            cameraExecutor,
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val bitmap = image.toBitmap()
                    image.close()
                    if (bitmap != null) {
                        continuation.resumeWith(Result.success(bitmap))
                    } else {
                        continuation.resumeWith(Result.failure(Exception("无法转换图片")))
                    }
                }

                override fun onError(exception: ImageCaptureException) {
                    Log.e(TAG, "拍照失败: ${exception.message}")
                    continuation.resumeWith(Result.failure(exception))
                }
            }
        )
    }

    /** 切换闪光灯模式 */
    fun setFlashMode(mode: Int) {
        imageCapture?.flashMode = mode
    }

    /** 设置缩放 */
    fun setZoom(scale: Float) {
        camera?.cameraControl?.setZoomRatio(scale.coerceIn(
            camera?.cameraInfo?.zoomState?.value?.minZoomRatio ?: 1f,
            camera?.cameraInfo?.zoomState?.value?.maxZoomRatio ?: 1f
        ))
    }

    /** 关闭相机 */
    fun shutdown() {
        cameraProvider?.unbindAll()
        cameraExecutor.shutdown()
        frameChannel.close()
        Log.i(TAG, "相机已关闭")
    }
}

// =============================================================================
// 扩展函数
// =============================================================================

/**
 * ImageProxy 转 Bitmap
 */
fun ImageProxy.toBitmap(): Bitmap? {
    return if (format == ImageFormat.YUV_420_888) {
        yuvToBitmap(this)
    } else {
        null
    }
}

private fun yuvToBitmap(image: ImageProxy): Bitmap? {
    val yBuffer = image.planes[0].buffer
    val uBuffer = image.planes[1].buffer
    val vBuffer = image.planes[2].buffer

    val ySize = yBuffer.remaining()
    val uSize = uBuffer.remaining()
    val vSize = vBuffer.remaining()

    val nv21 = ByteArray(ySize + uSize + vSize)
    yBuffer.get(nv21, 0, ySize)
    vBuffer.get(nv21, ySize, vSize)
    uBuffer.get(nv21, ySize + vSize, uSize)

    val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
    val out = ByteArrayOutputStream()
    yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), 100, out)
    val jpegBytes = out.toByteArray()
    return BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.size)
}

/**
 * ListenableFuture 转 suspend 函数
 */
private suspend fun <T> com.google.common.util.concurrent.ListenableFuture<T>.await(): T =
    suspendCancellableCoroutine { cont ->
        addListener({
            try {
                cont.resumeWith(Result.success(get()))
            } catch (e: Exception) {
                cont.resumeWith(Result.failure(e))
            }
        }, ContextCompat.getMainExecutor(cont.context as Context))
    }

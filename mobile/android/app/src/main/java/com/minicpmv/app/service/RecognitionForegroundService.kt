package com.minicpmv.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.minicpmv.app.MainActivity
import com.minicpmv.app.R
import com.minicpmv.app.camera.CameraManager
import com.minicpmv.app.data.entity.RecognitionRecord
import com.minicpmv.app.data.entity.SettingKeys
import com.minicpmv.app.inference.InferenceResult
import com.minicpmv.app.inference.OnnxInferenceEngine
import kotlinx.coroutines.*
import java.security.MessageDigest

/**
 * 后台识别 Foreground Service
 *
 * 职责:
 * - 以前台服务形式保持存活，定时拍照并识别
 * - 绑定 CameraManager 获取实时帧
 * - 绑定 OnnxInferenceEngine 执行推理
 * - 将结果写入 Room 数据库
 * - 通过通知栏展示识别结果
 *
 * 声明权限: FOREGROUND_SERVICE, FOREGROUND_SERVICE_CAMERA
 */
class RecognitionForegroundService : Service() {

    companion object {
        private const val TAG = "RecognitionService"
        private const val CHANNEL_ID = "minicpmv_recognition"
        private const val NOTIFICATION_ID = 1001
        private const val INTERVAL_MS = 30000L  // 默认 30 秒识别一次

        fun start(context: Context) {
            val intent = Intent(context, RecognitionForegroundService::class.java)
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, RecognitionForegroundService::class.java))
        }
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var cameraManager: CameraManager? = null
    private var inferenceEngine: OnnxInferenceEngine? = null
    private var isRunning = false
    private var recognitionJob: Job? = null

    // Binder for Activity binding
    inner class LocalBinder : Binder() {
        fun getService(): RecognitionForegroundService = this@RecognitionForegroundService
    }

    private val binder = LocalBinder()

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "服务 onCreate")
        createNotificationChannel()
        cameraManager = CameraManager(this)
        inferenceEngine = OnnxInferenceEngine(this)
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "服务 onStartCommand")
        startForeground(NOTIFICATION_ID, buildNotification("后台识别运行中...", null))
        startRecognitionLoop()
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "服务 onDestroy")
        isRunning = false
        recognitionJob?.cancel()
        serviceScope.cancel()
        cameraManager?.shutdown()
        inferenceEngine?.close()
    }

    /** 获取运行状态 */
    fun isServiceRunning(): Boolean = isRunning

    // ------------------------------------------------------------------
    // 核心识别循环
    // ------------------------------------------------------------------

    private fun startRecognitionLoop() {
        if (isRunning) return
        isRunning = true

        recognitionJob = serviceScope.launch {
            while (isRunning && isActive) {
                try {
                    // 检查自动识别开关
                    val autoEnabled = checkAutoRecognitionEnabled()
                    if (!autoEnabled) {
                        delay(5000)
                        continue
                    }

                    // TODO: 后台识别需要 Surface，这里简化处理
                    // 实际场景应使用 ImageReader 或绑定虚拟 Surface
                    // 这里仅模拟推理流程
                    val result = simulateRecognition()
                    saveResult(result)

                    updateNotification("识别完成", result.answer)
                    delay(INTERVAL_MS)
                } catch (e: CancellationException) {
                    break
                } catch (e: Exception) {
                    Log.e(TAG, "识别循环异常: ${e.message}")
                    delay(10000) // 出错后 10 秒重试
                }
            }
        }
    }

    private suspend fun simulateRecognition(): InferenceResult {
        // 实际实现应从相机获取帧并推理
        // 这里返回模拟结果
        delay(500)
        return InferenceResult(
            answer = "后台识别: 检测到场景 (模拟)",
            confidence = 0.75f,
            latencyMs = 500,
            modelVersion = "4.6-onnx",
            success = true
        )
    }

    private suspend fun saveResult(result: InferenceResult) {
        try {
            val app = application as com.minicpmv.app.MiniCPMVApplication
            val dao = app.database.recognitionRecordDao()

            val record = RecognitionRecord(
                imageHash = "bg_${System.currentTimeMillis()}",
                imagePath = "",
                question = "自动识别",
                answer = result.answer,
                confidence = result.confidence,
                taskType = "background",
                synced = false
            )
            dao.insert(record)
            Log.i(TAG, "识别结果已保存: id=${record.id}")
        } catch (e: Exception) {
            Log.e(TAG, "保存结果失败: ${e.message}")
        }
    }

    private suspend fun checkAutoRecognitionEnabled(): Boolean {
        return try {
            val app = application as com.minicpmv.app.MiniCPMVApplication
            app.database.userSettingDao().getBoolean(SettingKeys.AUTO_RECOGNITION, false)
        } catch (e: Exception) {
            false
        }
    }

    // ------------------------------------------------------------------
    // 通知栏
    // ------------------------------------------------------------------

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "后台识别服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "MiniCPM-V 后台实时识别"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(title: String, content: String?): Notification {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(content ?: "正在运行后台识别...")
            .setSmallIcon(R.drawable.ic_notification) // 需添加图标资源
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }

    private fun updateNotification(title: String, content: String) {
        val notification = buildNotification(title, content)
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification)
    }

    // MD5 工具
    private fun md5(data: ByteArray): String {
        val digest = MessageDigest.getInstance("MD5")
        return digest.digest(data).joinToString("") { "%02x".format(it) }
    }
}

// ContextCompat.startForegroundService 兼容
private fun ContextCompat.startForegroundService(context: Context, intent: Intent) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        context.startForegroundService(intent)
    } else {
        context.startService(intent)
    }
}

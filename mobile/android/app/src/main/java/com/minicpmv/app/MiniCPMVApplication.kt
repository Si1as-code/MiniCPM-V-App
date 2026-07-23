package com.minicpmv.app

import android.app.Application
import android.util.Log
import com.minicpmv.app.data.AppDatabase
import com.minicpmv.app.inference.OnnxInferenceEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * MiniCPM-V Android 应用入口
 *
 * 职责:
 * - 全局应用状态初始化
 * - Room 数据库 (SQLCipher) 初始化
 * - ONNX Runtime 推理引擎预加载
 * - 全局 CoroutineScope (SupervisorJob)
 */
class MiniCPMVApplication : Application() {

    companion object {
        private const val TAG = "MiniCPMVApp"
    }

    /** 应用级协程作用域，子协程失败不影响其他协程 */
    val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** 延迟初始化数据库，首次访问时才创建 */
    val database by lazy {
        Log.i(TAG, "初始化 SQLCipher 数据库...")
        AppDatabase.getInstance(this)
    }

    /** 延迟初始化 ONNX 推理引擎 */
    val inferenceEngine by lazy {
        Log.i(TAG, "初始化 ONNX Runtime Mobile...")
        OnnxInferenceEngine(this)
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "MiniCPM-V 应用启动")

        // 异步预热推理引擎（在后台线程）
        applicationScope.launch(Dispatchers.IO) {
            try {
                inferenceEngine.warmup()
                Log.i(TAG, "ONNX 引擎预热完成")
            } catch (e: Exception) {
                Log.e(TAG, "ONNX 引擎预热失败: ${e.message}")
            }
        }
    }
}

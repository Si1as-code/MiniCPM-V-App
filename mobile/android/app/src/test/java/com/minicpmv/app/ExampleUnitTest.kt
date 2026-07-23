package com.minicpmv.app

import com.minicpmv.app.data.entity.RecognitionRecord
import com.minicpmv.app.data.entity.SettingKeys
import com.minicpmv.app.data.entity.UserSetting
import com.minicpmv.app.inference.InferenceResult
import com.minicpmv.app.network.*
import org.junit.Assert.*
import org.junit.Test

/**
 * Android 客户端单元测试
 */
class ExampleUnitTest {

    // ==================== 数据实体测试 ====================

    @Test
    fun recognitionRecord_defaultValues() {
        val record = RecognitionRecord(
            id = 1,
            imageHash = "abc123",
            imagePath = "/path/to/image.jpg",
            question = "这是什么？",
            answer = "这是一只猫",
            confidence = 0.92f
        )
        assertEquals(1L, record.id)
        assertEquals("abc123", record.imageHash)
        assertEquals("4.6", record.modelVersion)
        assertEquals("local", record.taskType)
        assertFalse(record.synced)
        assertTrue(record.createdAt > 0)
    }

    @Test
    fun userSetting_keysAreUnique() {
        val keys = listOf(
            SettingKeys.AUTO_RECOGNITION,
            SettingKeys.CLOUD_ENABLED,
            SettingKeys.DAILY_BUDGET,
            SettingKeys.CONFIDENCE_THRESHOLD,
            SettingKeys.USER_TOKEN
        )
        assertEquals(keys.size, keys.toSet().size)
    }

    @Test
    fun userSetting_booleanConversion() {
        val setting = UserSetting(key = "test_bool", value = "true")
        assertTrue(setting.value.toBoolean())

        val falseSetting = UserSetting(key = "test_bool2", value = "false")
        assertFalse(falseSetting.value.toBoolean())
    }

    // ==================== 推理结果测试 ====================

    @Test
    fun inferenceResult_successState() {
        val result = InferenceResult(
            answer = "识别结果",
            confidence = 0.85f,
            latencyMs = 1234,
            modelVersion = "4.6-onnx",
            success = true
        )
        assertTrue(result.success)
        assertEquals("识别结果", result.answer)
        assertEquals(0.85f, result.confidence, 0.01f)
        assertNull(result.errorMessage)
    }

    @Test
    fun inferenceResult_failureState() {
        val result = InferenceResult(
            answer = "识别失败",
            confidence = 0f,
            latencyMs = 0,
            modelVersion = "",
            success = false,
            errorMessage = "模型未加载"
        )
        assertFalse(result.success)
        assertEquals("模型未加载", result.errorMessage)
    }

    // ==================== 网络数据类测试 ====================

    @Test
    fun inferenceRequest_defaultValues() {
        val request = InferenceRequest(image_base64 = "base64string")
        assertEquals("描述这张图片", request.question)
        assertEquals("4.6", request.model_version)
        assertFalse(request.force_local)
    }

    @Test
    fun inferenceResponse_parsing() {
        val response = InferenceResponse(
            answer = "测试结果",
            confidence = 0.9f,
            model_version = "4.6",
            latency_ms = 500,
            task_type = "local"
        )
        assertEquals("测试结果", response.answer)
        assertEquals("local", response.task_type)
    }

    @Test
    fun syncResponse_calculation() {
        val response = SyncResponse(uploaded = 10, conflicts = 2, message = "同步完成")
        assertEquals(10, response.uploaded)
        assertEquals(2, response.conflicts)
    }

    @Test
    fun dailyStatItem_format() {
        val item = DailyStatItem(date = "2024-01-15", count = 5, cost = 0.5f)
        assertEquals("2024-01-15", item.date)
        assertEquals(5, item.count)
    }

    // ==================== 工具方法测试 ====================

    @Test
    fun confidenceProgress_calculation() {
        val confidence = 0.85f
        val progress = (confidence * 100).toInt()
        assertEquals(85, progress)
    }

    @Test
    fun timestampToDate_format() {
        val timestamp = 1705315200000L // 2024-01-15 00:00:00 UTC
        val date = java.util.Date(timestamp)
        val formatter = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault())
        assertEquals("2024-01-15", formatter.format(date))
    }
}

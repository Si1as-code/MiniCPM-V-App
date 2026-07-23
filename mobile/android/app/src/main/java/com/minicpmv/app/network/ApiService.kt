package com.minicpmv.app.network

import com.minicpmv.app.data.entity.RecognitionRecord
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Query

/**
 * Retrofit API 接口 - 对接 Sprint 4 后端服务
 */
interface ApiService {

    // ==================== 推理 API ====================

    @POST("/api/inference/sync")
    suspend fun inferenceSync(
        @Header("Authorization") token: String,
        @Body request: InferenceRequest
    ): Response<InferenceResponse>

    @POST("/api/inference/async")
    suspend fun inferenceAsync(
        @Header("Authorization") token: String,
        @Body request: InferenceRequest
    ): Response<TaskResponse>

    // ==================== 任务管理 ====================

    @GET("/api/tasks")
    suspend fun getTasks(
        @Header("Authorization") token: String,
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("offset") offset: Int = 0
    ): Response<TaskListResponse>

    // ==================== 统计 API ====================

    @GET("/api/stats")
    suspend fun getStats(
        @Header("Authorization") token: String
    ): Response<StatsResponse>

    @GET("/api/stats/daily")
    suspend fun getDailyStats(
        @Header("Authorization") token: String,
        @Query("start_date") startDate: String,
        @Query("end_date") endDate: String
    ): Response<DailyStatsResponse>

    // ==================== 同步 API ====================

    @POST("/api/sync/upload")
    suspend fun uploadRecords(
        @Header("Authorization") token: String,
        @Body records: List<RecognitionRecord>
    ): Response<SyncResponse>

    @GET("/api/sync/download")
    suspend fun downloadRecords(
        @Header("Authorization") token: String,
        @Query("since") since: Long = 0
    ): Response<List<RecognitionRecord>>
}

// =============================================================================
// 请求/响应数据类
// =============================================================================

data class InferenceRequest(
    val image_base64: String,
    val question: String = "描述这张图片",
    val model_version: String = "4.6",
    val force_local: Boolean = false
)

data class InferenceResponse(
    val answer: String,
    val confidence: Float,
    val model_version: String,
    val latency_ms: Int,
    val task_type: String  // local / cloud
)

data class TaskResponse(
    val task_id: String,
    val status: String,
    val message: String
)

data class TaskListResponse(
    val tasks: List<TaskItem>,
    val total: Int
)

data class TaskItem(
    val id: String,
    val status: String,
    val created_at: String,
    val completed_at: String? = null
)

data class StatsResponse(
    val total_inferences: Int,
    val local_inferences: Int,
    val cloud_inferences: Int,
    val avg_confidence: Float,
    val total_cost: Float
)

data class DailyStatsResponse(
    val daily: List<DailyStatItem>
)

data class DailyStatItem(
    val date: String,
    val count: Int,
    val cost: Float
)

data class SyncResponse(
    val uploaded: Int,
    val conflicts: Int,
    val message: String
)

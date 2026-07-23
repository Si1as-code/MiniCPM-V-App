package com.minicpmv.app.data.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * 识别记录实体 - 对应 SQLite 的 recognition_records 表
 */
@Entity(tableName = "recognition_records")
data class RecognitionRecord(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "image_hash")
    val imageHash: String,           // 图片 MD5 哈希，用于去重

    @ColumnInfo(name = "image_path")
    val imagePath: String,           // 本地图片路径

    @ColumnInfo(name = "question")
    val question: String,            // 用户问题

    @ColumnInfo(name = "answer")
    val answer: String,              // 模型回答

    @ColumnInfo(name = "confidence")
    val confidence: Float,           // 置信度 0.0~1.0

    @ColumnInfo(name = "model_version")
    val modelVersion: String = "4.6",// 模型版本

    @ColumnInfo(name = "device_id")
    val deviceId: String = "",       // 设备 ID（多设备区分）

    @ColumnInfo(name = "task_type")
    val taskType: String = "local",  // local / cloud / hybrid

    @ColumnInfo(name = "synced")
    val synced: Boolean = false,     // 是否已同步到云端

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
)

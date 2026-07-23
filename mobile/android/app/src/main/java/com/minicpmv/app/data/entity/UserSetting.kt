package com.minicpmv.app.data.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * 用户设置实体 - key-value 存储
 */
@Entity(tableName = "user_settings")
data class UserSetting(
    @PrimaryKey
    val key: String,                 // 设置键名

    @ColumnInfo(name = "value")
    val value: String,               // 设置值（JSON 序列化）

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
)

/** 常用设置键名常量 */
object SettingKeys {
    const val AUTO_RECOGNITION = "auto_recognition"      // 后台自动识别开关
    const val CLOUD_ENABLED = "cloud_enabled"            // 云端 API 开关
    const val DAILY_BUDGET = "daily_budget"              // 日预算（元）
    const val CONFIDENCE_THRESHOLD = "confidence_threshold" // 置信度阈值
    const val USER_TOKEN = "user_token"                  // JWT access_token
    const val REFRESH_TOKEN = "refresh_token"            // JWT refresh_token
    const val USER_ID = "user_id"                        // 用户 ID
    const val SYNC_WIFI_ONLY = "sync_wifi_only"          // 仅 WiFi 同步
    const val LAST_SYNC_TIME = "last_sync_time"          // 上次同步时间戳
}

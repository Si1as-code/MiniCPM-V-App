package com.minicpmv.app.data.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.minicpmv.app.data.entity.UserSetting

/**
 * 用户设置 DAO
 */
@Dao
interface UserSettingDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun set(setting: UserSetting)

    @Query("SELECT * FROM user_settings WHERE key = :key LIMIT 1")
    suspend fun get(key: String): UserSetting?

    @Query("DELETE FROM user_settings WHERE key = :key")
    suspend fun delete(key: String)

    // 便捷方法：获取布尔值
    suspend fun getBoolean(key: String, default: Boolean = false): Boolean {
        return get(key)?.value?.toBoolean() ?: default
    }

    // 便捷方法：获取字符串
    suspend fun getString(key: String, default: String = ""): String {
        return get(key)?.value ?: default
    }

    // 便捷方法：获取浮点数
    suspend fun getFloat(key: String, default: Float = 0f): Float {
        return get(key)?.value?.toFloatOrNull() ?: default
    }

    // 便捷方法：获取整数
    suspend fun getInt(key: String, default: Int = 0): Int {
        return get(key)?.value?.toIntOrNull() ?: default
    }

    // 便捷方法：获取长整数
    suspend fun getLong(key: String, default: Long = 0L): Long {
        return get(key)?.value?.toLongOrNull() ?: default
    }
}

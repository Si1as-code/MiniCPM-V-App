package com.minicpmv.app.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.minicpmv.app.data.dao.ConversationDao
import com.minicpmv.app.data.dao.RecognitionRecordDao
import com.minicpmv.app.data.dao.UserSettingDao
import com.minicpmv.app.data.entity.Conversation
import com.minicpmv.app.data.entity.RecognitionRecord
import com.minicpmv.app.data.entity.UserSetting
import net.zetetic.database.sqlcipher.SQLiteDatabase
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory

/**
 * Room 数据库 - SQLCipher 加密版本
 *
 * 数据库版本: 1
 * 表: recognition_records, conversations, user_settings
 */
@Database(
    entities = [RecognitionRecord::class, Conversation::class, UserSetting::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun recognitionRecordDao(): RecognitionRecordDao
    abstract fun conversationDao(): ConversationDao
    abstract fun userSettingDao(): UserSettingDao

    companion object {
        private const val DB_NAME = "minicpmv_encrypted.db"
        private const val DB_PASSWORD = "MiniCPM-V-Secure-Key-2024" // 生产环境应从 Keystore 获取

        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: buildDatabase(context).also { INSTANCE = it }
            }
        }

        private fun buildDatabase(context: Context): AppDatabase {
            // SQLCipher 加密配置
            System.loadLibrary("sqlcipher")
            val factory = SupportOpenHelperFactory(SQLiteDatabase.getBytes(DB_PASSWORD.toCharArray()))

            return Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                DB_NAME
            )
                .openHelperFactory(factory)
                .fallbackToDestructiveMigration(false)
                .build()
        }

        /** 仅测试使用：创建内存数据库 */
        fun createInMemory(context: Context): AppDatabase {
            return Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        }
    }
}

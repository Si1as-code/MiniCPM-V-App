package com.minicpmv.app.data.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.minicpmv.app.data.entity.Conversation
import kotlinx.coroutines.flow.Flow

/**
 * 对话消息 DAO
 */
@Dao
interface ConversationDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: Conversation): Long

    @Query("SELECT * FROM conversations WHERE record_id = :recordId ORDER BY created_at ASC")
    fun getByRecordId(recordId: Long): Flow<List<Conversation>>

    @Query("SELECT * FROM conversations WHERE record_id = :recordId ORDER BY created_at ASC")
    suspend fun getByRecordIdSync(recordId: Long): List<Conversation>

    @Query("DELETE FROM conversations WHERE record_id = :recordId")
    suspend fun deleteByRecordId(recordId: Long)

    @Query("SELECT COUNT(*) FROM conversations WHERE record_id = :recordId")
    suspend fun countByRecordId(recordId: Long): Int
}

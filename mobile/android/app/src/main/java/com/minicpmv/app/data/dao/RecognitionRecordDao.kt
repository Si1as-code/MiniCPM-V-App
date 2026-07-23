package com.minicpmv.app.data.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.minicpmv.app.data.entity.RecognitionRecord
import kotlinx.coroutines.flow.Flow

/**
 * 识别记录 DAO
 */
@Dao
interface RecognitionRecordDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(record: RecognitionRecord): Long

    @Update
    suspend fun update(record: RecognitionRecord)

    @Delete
    suspend fun delete(record: RecognitionRecord)

    @Query("SELECT * FROM recognition_records ORDER BY created_at DESC")
    fun getAll(): Flow<List<RecognitionRecord>>

    @Query("SELECT * FROM recognition_records WHERE id = :id")
    suspend fun getById(id: Long): RecognitionRecord?

    @Query("SELECT * FROM recognition_records WHERE image_hash = :hash LIMIT 1")
    suspend fun getByImageHash(hash: String): RecognitionRecord?

    @Query("SELECT * FROM recognition_records WHERE synced = 0 ORDER BY created_at ASC")
    suspend fun getUnsynced(): List<RecognitionRecord>

    @Query("UPDATE recognition_records SET synced = 1 WHERE id = :id")
    suspend fun markSynced(id: Long)

    @Query("SELECT COUNT(*) FROM recognition_records")
    suspend fun count(): Int

    @Query("DELETE FROM recognition_records WHERE created_at < :timestamp")
    suspend fun deleteOlderThan(timestamp: Long)

    @Query("SELECT * FROM recognition_records WHERE answer LIKE '%' || :query || '%' OR question LIKE '%' || :query || '%' ORDER BY created_at DESC")
    fun search(query: String): Flow<List<RecognitionRecord>>
}

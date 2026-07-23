package com.minicpmv.app.data.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * 对话消息实体 - 多轮问答的每一条消息
 */
@Entity(
    tableName = "conversations",
    foreignKeys = [
        ForeignKey(
            entity = RecognitionRecord::class,
            parentColumns = ["id"],
            childColumns = ["record_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("record_id")]
)
data class Conversation(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "record_id")
    val recordId: Long,              // 关联的识别记录 ID

    @ColumnInfo(name = "role")
    val role: String,                // "user" / "assistant" / "system"

    @ColumnInfo(name = "content")
    val content: String,             // 消息内容

    @ColumnInfo(name = "token_count")
    val tokenCount: Int = 0,         // token 数量（估算）

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis()
)

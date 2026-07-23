package com.minicpmv.app.viewmodel

import android.app.Application
import android.graphics.Bitmap
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.minicpmv.app.data.entity.Conversation
import com.minicpmv.app.data.entity.RecognitionRecord
import com.minicpmv.app.data.entity.SettingKeys
import com.minicpmv.app.data.entity.UserSetting
import com.minicpmv.app.inference.InferenceResult
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

/**
 * 主 ViewModel - 管理相机、推理、历史记录的状态
 */
class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val app = application as com.minicpmv.app.MiniCPMVApplication
    private val recordDao = app.database.recognitionRecordDao()
    private val conversationDao = app.database.conversationDao()
    private val settingDao = app.database.userSettingDao()
    private val inferenceEngine = app.inferenceEngine

    // ==================== 相机状态 ====================
    private val _cameraReady = mutableStateOf(false)
    val cameraReady: State<Boolean> = _cameraReady

    fun setCameraReady(ready: Boolean) {
        _cameraReady.value = ready
    }

    // ==================== 推理状态 ====================
    private val _isInferencing = mutableStateOf(false)
    val isInferencing: State<Boolean> = _isInferencing

    private val _lastResult = mutableStateOf<InferenceResult?>(null)
    val lastResult: State<InferenceResult?> = _lastResult

    private val _currentRecordId = mutableStateOf<Long?>(null)
    val currentRecordId: State<Long?> = _currentRecordId

    /** 执行推理 */
    fun runInference(bitmap: Bitmap, question: String = "描述这张图片") {
        viewModelScope.launch {
            _isInferencing.value = true
            try {
                val result = inferenceEngine.inference(bitmap, question)
                _lastResult.value = result

                // 保存到数据库
                if (result.success) {
                    val record = RecognitionRecord(
                        imageHash = bitmap.hashCode().toString(), // 简化哈希
                        imagePath = "",
                        question = question,
                        answer = result.answer,
                        confidence = result.confidence,
                        taskType = "local"
                    )
                    val id = recordDao.insert(record)
                    _currentRecordId.value = id

                    // 保存对话记录
                    conversationDao.insert(Conversation(
                        recordId = id,
                        role = "user",
                        content = question
                    ))
                    conversationDao.insert(Conversation(
                        recordId = id,
                        role = "assistant",
                        content = result.answer
                    ))
                }
            } catch (e: Exception) {
                _lastResult.value = InferenceResult(
                    answer = "推理异常: ${e.message}",
                    confidence = 0f,
                    latencyMs = 0,
                    modelVersion = "",
                    success = false
                )
            } finally {
                _isInferencing.value = false
            }
        }
    }

    // ==================== 历史记录 ====================
    val historyRecords: StateFlow<List<RecognitionRecord>> = recordDao.getAll()
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery.asStateFlow()

    val searchResults: StateFlow<List<RecognitionRecord>> = _searchQuery
        .flatMapLatest { query ->
            if (query.isBlank()) {
                recordDao.getAll()
            } else {
                recordDao.search(query)
            }
        }
        .stateIn(viewModelScope, SharingStarted.Lazily, emptyList())

    fun setSearchQuery(query: String) {
        _searchQuery.value = query
    }

    fun deleteRecord(record: RecognitionRecord) {
        viewModelScope.launch {
            recordDao.delete(record)
        }
    }

    // ==================== 对话 ====================
    fun getConversations(recordId: Long): Flow<List<Conversation>> {
        return conversationDao.getByRecordId(recordId)
    }

    fun sendMessage(recordId: Long, content: String) {
        viewModelScope.launch {
            conversationDao.insert(Conversation(
                recordId = recordId,
                role = "user",
                content = content
            ))
            // TODO: 调用推理引擎生成回复
            conversationDao.insert(Conversation(
                recordId = recordId,
                role = "assistant",
                content = "[自动回复] 这是基于上下文的回答..."
            ))
        }
    }

    // ==================== 设置 ====================
    private val _settings = MutableStateFlow<Map<String, String>>(emptyMap())

    fun loadSettings() {
        viewModelScope.launch {
            // 加载常用设置
            val keys = listOf(
                SettingKeys.AUTO_RECOGNITION,
                SettingKeys.CLOUD_ENABLED,
                SettingKeys.CONFIDENCE_THRESHOLD,
                SettingKeys.SYNC_WIFI_ONLY
            )
            val map = mutableMapOf<String, String>()
            keys.forEach { key ->
                map[key] = settingDao.getString(key)
            }
            _settings.value = map
        }
    }

    fun getSettingBoolean(key: String, default: Boolean = false): Boolean {
        return _settings.value[key]?.toBoolean() ?: default
    }

    fun setSetting(key: String, value: String) {
        viewModelScope.launch {
            settingDao.set(UserSetting(key = key, value = value))
            _settings.value = _settings.value.toMutableMap().apply { put(key, value) }
        }
    }

    // ==================== 同步 ====================
    private val _syncState = mutableStateOf<SyncState>(SyncState.Idle)
    val syncState: State<SyncState> = _syncState

    fun triggerSync() {
        viewModelScope.launch {
            _syncState.value = SyncState.Syncing
            try {
                // TODO: 调用 Retrofit 同步 API
                val unsynced = recordDao.getUnsynced()
                // 模拟同步
                unsynced.forEach { recordDao.markSynced(it.id) }
                _syncState.value = SyncState.Success("同步完成，${unsynced.size} 条记录")
            } catch (e: Exception) {
                _syncState.value = SyncState.Error(e.message ?: "同步失败")
            }
        }
    }

    sealed class SyncState {
        data object Idle : SyncState()
        data object Syncing : SyncState()
        data class Success(val message: String) : SyncState()
        data class Error(val message: String) : SyncState()
    }
}

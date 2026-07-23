"""
============================================================================
数据模型 - 6 张核心表的 dataclass 定义
============================================================================
对应数据库表结构，用于类型安全和 IDE 补全。
============================================================================
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import time


@dataclass
class RecognitionRecord:
    """识别记录 - 核心数据表"""
    id: Optional[int] = None
    image_hash: str = ""
    image_path: str = ""
    question: str = ""
    answer: str = ""
    confidence: float = 0.0
    model_version: str = ""
    device_id: str = ""
    task_type: str = "auto"  # describe / ocr / qa / classify / auto
    synced: int = 0  # 0=未同步, 1=已同步
    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_hash": self.image_hash,
            "image_path": self.image_path,
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "device_id": self.device_id,
            "task_type": self.task_type,
            "synced": self.synced,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Conversation:
    """多轮对话记录"""
    id: Optional[int] = None
    record_id: int = 0  # 关联 recognition_records.id
    role: str = "user"  # user / assistant / system
    content: str = ""
    token_count: int = 0
    created_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "role": self.role,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at,
        }


@dataclass
class ImageIndex:
    """图片向量索引（预留，用于语义搜索）"""
    id: Optional[int] = None
    image_hash: str = ""
    embedding_vector: Optional[bytes] = None  # BLOB
    embedding_version: str = ""
    indexed_at: Optional[float] = None

    def __post_init__(self):
        if self.indexed_at is None:
            self.indexed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "image_hash": self.image_hash,
            "embedding_version": self.embedding_version,
            "indexed_at": self.indexed_at,
        }


@dataclass
class APITask:
    """云端 API 任务队列"""
    id: Optional[int] = None
    record_id: Optional[int] = None  # 关联 recognition_records.id
    provider: str = ""  # qwen / doubao / openai
    status: str = "pending"  # pending / running / completed / failed / cancelled
    retry_count: int = 0
    last_error: str = ""
    scheduled_at: Optional[float] = None
    completed_at: Optional[float] = None
    created_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.scheduled_at is None:
            self.scheduled_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "provider": self.provider,
            "status": self.status,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "scheduled_at": self.scheduled_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


@dataclass
class UserSetting:
    """用户设置 - key-value 存储"""
    key: str = ""
    value: str = ""
    updated_at: Optional[float] = None

    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at,
        }


@dataclass
class UsageStat:
    """使用统计 - 按天聚合"""
    id: Optional[int] = None
    date: str = ""  # YYYY-MM-DD
    local_count: int = 0
    api_count: int = 0
    tokens_used: int = 0
    cost: float = 0.0
    created_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "local_count": self.local_count,
            "api_count": self.api_count,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "created_at": self.created_at,
        }

"""
============================================================================
数据持久层模块
============================================================================
用法:
    from data import init_database, recognition_dao, conversation_dao
    from data import settings_dao, usage_dao, api_task_dao
    from data import db_manager

    # 初始化数据库
    init_database()

    # 使用 DAO
    record_id = recognition_dao.insert(recognition_record)
    conversations = conversation_dao.get_by_record_id(record_id)
============================================================================
"""

from data.database import DatabaseManager, DAOBase, db_manager
from data.models import (
    RecognitionRecord,
    Conversation,
    ImageIndex,
    APITask,
    UserSetting,
    UsageStat,
)
from data.dao_recognition import RecognitionDAO, recognition_dao
from data.dao_conversation import ConversationDAO, conversation_dao
from data.dao_api_tasks import APITaskDAO, api_task_dao
from data.dao_settings import SettingsDAO, settings_dao
from data.dao_usage import UsageDAO, usage_dao
from data.migrations import init_database, reset_database

__all__ = [
    # 数据库管理
    "DatabaseManager",
    "DAOBase",
    "db_manager",
    # 数据模型
    "RecognitionRecord",
    "Conversation",
    "ImageIndex",
    "APITask",
    "UserSetting",
    "UsageStat",
    # DAO
    "RecognitionDAO",
    "recognition_dao",
    "ConversationDAO",
    "conversation_dao",
    "APITaskDAO",
    "api_task_dao",
    "SettingsDAO",
    "settings_dao",
    "UsageDAO",
    "usage_dao",
    # 迁移
    "init_database",
    "reset_database",
]

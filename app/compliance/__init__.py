"""
Sprint 8: 合规模块

包含：
- 隐私政策与用户协议生成
- GDPR / 个人信息保护法数据合规
- Google Play / App Store 上架合规清单
"""

from .privacy_policy import PrivacyPolicyGenerator, PrivacyPolicyConfig
from .data_compliance import DataComplianceManager, DataExportRequest, DataDeletionRequest
from .store_checklist import StoreChecklistValidator, ChecklistItem, StoreType

__all__ = [
    "PrivacyPolicyGenerator",
    "PrivacyPolicyConfig",
    "DataComplianceManager",
    "DataExportRequest",
    "DataDeletionRequest",
    "StoreChecklistValidator",
    "ChecklistItem",
    "StoreType",
]

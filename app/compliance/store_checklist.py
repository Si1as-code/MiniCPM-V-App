"""
应用商店合规清单验证器

覆盖 Google Play 和 Apple App Store 的上架合规要求。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StoreType(Enum):
    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "n/a"


@dataclass
class ChecklistItem:
    """清单条目"""
    id: str
    category: str
    title: str
    description: str
    status: CheckStatus = CheckStatus.FAIL
    detail: str = ""
    required: bool = True
    store: StoreType = StoreType.GOOGLE_PLAY


class StoreChecklistValidator:
    """应用商店合规清单验证器"""

    def __init__(self):
        self._items: list[ChecklistItem] = []
        self._init_checklist()

    def _init_checklist(self):
        """初始化合规清单"""
        # ===== 通用合规 =====
        common = [
            ("privacy_policy_url", "合规文档", "隐私政策 URL",
             "提供可公开访问的隐私政策 URL", StoreType.GOOGLE_PLAY),
            ("privacy_policy_url_ios", "合规文档", "隐私政策 URL",
             "App Store Connect 中填写隐私政策 URL", StoreType.APP_STORE),
            ("user_agreement", "合规文档", "用户协议",
             "提供用户服务协议文档", StoreType.GOOGLE_PLAY),
            ("data_safety_form", "合规文档", "数据安全表单",
             "Google Play Data Safety 表单已填写", StoreType.GOOGLE_PLAY),
            ("app_privacy_details", "合规文档", "App 隐私详情",
             "App Store 隐私详情问卷已填写", StoreType.APP_STORE),
        ]

        # ===== 权限说明 =====
        permissions = [
            ("camera_justification", "权限", "相机权限说明",
             "说明为何需要相机权限（AI 视觉识别）", StoreType.GOOGLE_PLAY),
            ("camera_usage_desc", "权限", "相机使用描述",
             "Info.plist NSCameraUsageDescription 已配置", StoreType.APP_STORE),
            ("photo_library_justification", "权限", "相册权限说明",
             "说明为何需要相册权限（图片识别）", StoreType.GOOGLE_PLAY),
            ("photo_usage_desc", "权限", "相册使用描述",
             "Info.plist NSPhotoLibraryUsageDescription 已配置", StoreType.APP_STORE),
            ("background_mode_justification", "权限", "后台模式说明",
             "说明为何需要后台运行（持续识别任务）", StoreType.APP_STORE),
        ]

        # ===== 数据安全 =====
        data_security = [
            ("data_encryption", "数据安全", "数据加密声明",
             "声明应用使用数据加密（SQLCipher / Data Protection）", StoreType.GOOGLE_PLAY),
            ("data_deletion_api", "数据安全", "数据删除 API",
             "提供用户数据删除接口（满足 GDPR 被遗忘权）", StoreType.GOOGLE_PLAY),
            ("account_deletion_api", "数据安全", "账户删除功能",
             "提供账户删除功能（App Store 强制要求）", StoreType.APP_STORE),
            ("data_export_api", "数据安全", "数据导出功能",
             "提供用户数据导出功能（GDPR 数据可携带权）", StoreType.GOOGLE_PLAY),
            ("encryption_attestation", "数据安全", "加密证明",
             "App Store 加密出口合规证明已提交", StoreType.APP_STORE),
        ]

        # ===== 内容分级 =====
        content_rating = [
            ("content_rating", "内容分级", "内容分级问卷",
             "IARC 内容分级问卷已完成", StoreType.GOOGLE_PLAY),
            ("age_rating", "内容分级", "年龄分级",
             "App Store 年龄分级已设置（建议 12+）", StoreType.APP_STORE),
            ("ai_content_policy", "内容分级", "AI 内容政策",
             "AI 生成内容披露已配置", StoreType.GOOGLE_PLAY),
        ]

        # ===== 技术要求 =====
        technical = [
            ("target_sdk", "技术要求", "Target SDK 版本",
             "Android targetSdkVersion >= 34 (Android 14)", StoreType.GOOGLE_PLAY),
            ("min_sdk", "技术要求", "Min SDK 版本",
             "Android minSdkVersion >= 26 (Android 8.0)", StoreType.GOOGLE_PLAY),
            ("ios_min_version", "技术要求", "iOS 最低版本",
             "iOS Deployment Target >= 17.0", StoreType.APP_STORE),
            ("app_size_optimization", "技术要求", "包体优化",
             "AAB 分包 / App Thinning 已配置", StoreType.GOOGLE_PLAY),
            ("64bit_support", "技术要求", "64 位支持",
             "提供 64 位架构支持（arm64 / x86_64）", StoreType.APP_STORE),
            ("crash_free_rate", "技术要求", "崩溃率",
             "崩溃率 < 0.1%（Crashlytics 验证）", StoreType.GOOGLE_PLAY),
        ]

        # ===== 商店资源 =====
        store_assets = [
            ("app_icon_512", "商店资源", "应用图标 512x512",
             "Google Play 应用图标 512x512 PNG", StoreType.GOOGLE_PLAY),
            ("app_icon_1024", "商店资源", "应用图标 1024x1024",
             "App Store 应用图标 1024x1024 PNG（无圆角无 alpha）", StoreType.APP_STORE),
            ("screenshots_phone", "商店资源", "手机截图",
             "至少 2 张手机截图（最低 320px，最高 3840px）", StoreType.GOOGLE_PLAY),
            ("screenshots_ios", "商店资源", "iOS 截图",
             "至少 6.7 寸和 6.5 寸设备截图各一套", StoreType.APP_STORE),
            ("feature_graphic", "商店资源", "置顶大图",
             "Google Play Feature Graphic 1024x500", StoreType.GOOGLE_PLAY),
            ("app_description", "商店资源", "应用描述",
             "应用描述 80-4000 字符（中文）", StoreType.GOOGLE_PLAY),
            ("short_description", "商店资源", "简短描述",
             "Google Play 简短描述 <= 80 字符", StoreType.GOOGLE_PLAY),
            ("app_preview_video", "商店资源", "预览视频",
             "App Store 预览视频 15-30 秒（可选但推荐）", StoreType.APP_STORE),
        ]

        for item_list in [common, permissions, data_security, content_rating, technical, store_assets]:
            for item_id, category, title, desc, store in item_list:
                self._items.append(ChecklistItem(
                    id=item_id, category=category, title=title,
                    description=desc, store=store,
                ))

    def check(self, item_id: str, status: CheckStatus, detail: str = "") -> bool:
        """标记某项检查结果"""
        for item in self._items:
            if item.id == item_id:
                item.status = status
                item.detail = detail
                return True
        return False

    def validate_all(self, checks: dict[str, tuple[CheckStatus, str]]) -> int:
        """批量验证所有项，返回未通过数"""
        for item_id, (status, detail) in checks.items():
            self.check(item_id, status, detail)
        return self.get_fail_count()

    def get_report(self, store: Optional[StoreType] = None) -> dict:
        """获取合规报告"""
        items = self._items if store is None else [i for i in self._items if i.store == store]
        total = len(items)
        passed = sum(1 for i in items if i.status == CheckStatus.PASS)
        failed = sum(1 for i in items if i.status == CheckStatus.FAIL and i.required)
        warnings = sum(1 for i in items if i.status == CheckStatus.WARNING)

        categories = {}
        for item in items:
            if item.category not in categories:
                categories[item.category] = {"total": 0, "passed": 0, "failed": 0}
            categories[item.category]["total"] += 1
            if item.status == CheckStatus.PASS:
                categories[item.category]["passed"] += 1
            elif item.status == CheckStatus.FAIL and item.required:
                categories[item.category]["failed"] += 1

        return {
            "total_items": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "0%",
            "ready_for_submission": failed == 0,
            "categories": categories,
            "failed_items": [
                {"id": i.id, "title": i.title, "description": i.description, "detail": i.detail}
                for i in items if i.status == CheckStatus.FAIL and i.required
            ],
        }

    def get_fail_count(self) -> int:
        """获取未通过的必需项数量"""
        return sum(1 for i in self._items if i.status == CheckStatus.FAIL and i.required)

    def get_checklist_markdown(self, store: Optional[StoreType] = None) -> str:
        """生成 Markdown 格式的清单"""
        items = self._items if store is None else [i for i in self._items if i.store == store]
        store_name = "全部" if store is None else store.value

        lines = [f"# 应用商店合规清单 ({store_name})\n"]
        current_category = ""

        for item in items:
            if item.category != current_category:
                current_category = item.category
                lines.append(f"\n## {current_category}\n")

            status_icon = {
                CheckStatus.PASS: "[x]",
                CheckStatus.FAIL: "[ ]",
                CheckStatus.WARNING: "[!]",
                CheckStatus.NOT_APPLICABLE: "[-]",
            }.get(item.status, "[ ]")

            required_tag = "" if item.required else " (可选)"
            lines.append(f"- {status_icon} **{item.title}**{required_tag}: {item.description}")
            if item.detail:
                lines.append(f"  - {item.detail}")

        report = self.get_report(store)
        lines.append(f"\n---\n\n**通过率**: {report['pass_rate']} "
                      f"({report['passed']}/{report['total_items']})\n"
                      f"**可提交审核**: {'是' if report['ready_for_submission'] else '否'}")

        return "\n".join(lines)

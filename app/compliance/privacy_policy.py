"""
隐私政策与用户协议生成器

根据应用实际数据采集行为，自动生成符合 GDPR 和
《个人信息保护法》要求的隐私政策文档。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class PrivacyPolicyConfig:
    """隐私政策配置"""

    app_name: str = "MiniCPM-V 端侧视觉助手"
    app_version: str = "1.0.0"
    company_name: str = "MiniCPM-V Team"
    contact_email: str = "privacy@minicpmv.app"
    company_address: str = "中国"
    effective_date: str = field(default_factory=lambda: date.today().isoformat())

    # 数据采集行为
    collects_camera_data: bool = True
    collects_location: bool = False
    collects_analytics: bool = True
    collects_crash_logs: bool = True
    collects_device_info: bool = True
    collects_usage_stats: bool = True

    # 数据存储
    local_storage_only: bool = False  # 是否仅本地存储
    cloud_sync_enabled: bool = True
    encryption_at_rest: bool = True
    encryption_in_transit: bool = True

    # 第三方服务
    third_party_services: list = field(
        default_factory=lambda: [
            {"name": "Firebase Crashlytics", "purpose": "崩溃监控", "data": "崩溃日志、设备型号、OS版本"},
            {"name": "阿里云 OSS", "purpose": "图片存储", "data": "用户拍摄的图片"},
            {"name": "通义千问 VL", "purpose": "云端视觉理解", "data": "图片和识别问题"},
            {"name": "Sentry", "purpose": "性能监控", "data": "性能指标、错误堆栈"},
        ]
    )

    # 用户权利
    supports_data_export: bool = True
    supports_data_deletion: bool = True
    supports_account_deletion: bool = True


class PrivacyPolicyGenerator:
    """隐私政策文档生成器"""

    def __init__(self, config: PrivacyPolicyConfig):
        self.config = config

    def generate_markdown(self) -> str:
        """生成 Markdown 格式的隐私政策"""
        sections = [
            self._header(),
            self._introduction(),
            self._data_collection(),
            self._data_usage(),
            self._data_storage(),
            self._third_party(),
            self._user_rights(),
            self._data_retention(),
            self._children_privacy(),
            self._policy_changes(),
            self._contact(),
        ]
        return "\n\n".join(sections)

    def generate_html(self) -> str:
        """生成 HTML 格式的隐私政策"""
        md = self.generate_markdown()
        html_parts = ["<!DOCTYPE html>", "<html lang='zh-CN'>", "<head>",
                       "<meta charset='UTF-8'>", "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
                       f"<title>隐私政策 - {self.config.app_name}</title>",
                       "<style>",
                       "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
                       "max-width: 800px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.6; }",
                       "h1 { color: #2563EB; } h2 { color: #1e40af; margin-top: 2rem; }",
                       "table { border-collapse: collapse; width: 100%; margin: 1rem 0; }",
                       "th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }",
                       "th { background: #f0f4ff; }", "code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }",
                       "</style>", "</head>", "<body>"]

        # Simple markdown to HTML conversion
        for line in md.split("\n"):
            if line.startswith("# "):
                html_parts.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_parts.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_parts.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("- "):
                html_parts.append(f"<li>{line[2:]}</li>")
            elif line.startswith("|"):
                # Table row - skip for simplicity, will be handled below
                html_parts.append(line)
            elif line.strip():
                html_parts.append(f"<p>{line}</p>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def generate_user_agreement(self) -> str:
        """生成用户协议"""
        return f"""# 用户协议

## 1. 协议接受

欢迎使用 {self.config.app_name}（以下简称"本应用"）。使用本应用即表示您同意本协议的全部条款。如果您不同意任何条款，请立即停止使用。

## 2. 服务描述

本应用提供基于端侧 AI 模型的实时拍照识别和多轮问答功能，支持端侧推理与云端 API 协同。

## 3. 用户责任

- 您应合法使用本应用，不得用于违法用途
- 您应确保拍摄内容不侵犯他人隐私权
- 您不得逆向工程、反编译或篡改应用
- 您不得滥用 API 调用额度

## 4. 知识产权

本应用及其 AI 模型（MiniCPM-V 4.6）的知识产权归 {self.config.company_name} 及相关权利人所有。

## 5. 免责声明

- 本应用提供的识别结果仅供参考，不构成专业建议
- {self.config.company_name} 不对识别结果的准确性作任何保证
- 因网络、设备等原因导致的服务中断，{self.config.company_name} 不承担责任

## 6. 协议变更

{self.config.company_name} 保留随时修改本协议的权利。重大变更将提前通知用户。

## 7. 终止

{self.config.company_name} 保留在用户违反协议时终止服务的权利。

## 8. 适用法律

本协议适用 {self.config.company_address} 法律。

---

生效日期：{self.config.effective_date}
联系邮箱：{self.config.contact_email}
"""

    def _header(self) -> str:
        return (f"# 隐私政策\n\n"
                f"**应用名称**: {self.config.app_name}\n"
                f"**版本**: {self.config.app_version}\n"
                f"**生效日期**: {self.config.effective_date}\n"
                f"**运营方**: {self.config.company_name}")

    def _introduction(self) -> str:
        return (f"## 1. 引言\n\n"
                f'{self.config.company_name}（以下简称"我们"）深知个人信息对您的重要性，'
                f"我们将按照《中华人民共和国个人信息保护法》、《GDPR》及相关法律法规，"
                f"保护您的个人信息。本政策说明我们如何收集、使用、存储和保护您的信息。")

    def _data_collection(self) -> str:
        items = ["## 2. 我们收集的信息\n"]
        if self.config.collects_camera_data:
            items.append("- **相机数据**: 您拍摄的照片和视频，用于 AI 视觉识别")
        if self.config.collects_device_info:
            items.append("- **设备信息**: 设备型号、操作系统版本、唯一设备标识，用于服务优化")
        if self.config.collects_usage_stats:
            items.append("- **使用统计**: 识别次数、推理耗时、API 调用量，用于性能优化")
        if self.config.collects_crash_logs:
            items.append("- **崩溃日志**: 应用崩溃时的堆栈信息，用于问题诊断")
        if self.config.collects_analytics:
            items.append("- **分析数据**: 功能使用频率、用户行为路径，用于产品改进")
        if self.config.collects_location:
            items.append("- **位置信息**: 大致位置（可选），用于场景识别增强")
        items.append("\n> **端侧优先**: 默认情况下，所有识别在设备本地完成，数据不上传云端。"
                      "仅当您选择云端识别或开启同步时，相关数据才会传输。")
        return "\n".join(items)

    def _data_usage(self) -> str:
        return ("## 3. 信息使用\n\n"
                "我们收集的信息仅用于：\n"
                "- 提供 AI 视觉识别和多轮问答功能\n"
                "- 优化端侧推理性能和准确率\n"
                "- 诊断和修复应用崩溃及性能问题\n"
                "- 防止滥用和欺诈行为\n\n"
                "> 我们不会将您的信息出售给第三方，也不会用于定向广告。")

    def _data_storage(self) -> str:
        parts = ["## 4. 信息存储\n"]
        if self.config.encryption_at_rest:
            parts.append("- **静态加密**: 本地数据库使用 AES-256 加密（SQLCipher / Data Protection）")
        if self.config.encryption_in_transit:
            parts.append("- **传输加密**: 所有网络通信使用 TLS 1.2+ 加密")
        if self.config.local_storage_only:
            parts.append("- **仅本地存储**: 您的所有数据仅保存在设备本地")
        else:
            parts.append("- **本地存储**: 识别记录、对话历史、用户设置保存在设备本地")
            if self.config.cloud_sync_enabled:
                parts.append("- **云端存储**: 当您开启同步时，数据将同步至云端 PostgreSQL 数据库")
        parts.append(f"\n**数据存储位置**: {self.config.company_address}")
        return "\n".join(parts)

    def _third_party(self) -> str:
        parts = ["## 5. 第三方服务\n\n", "| 服务名称 | 用途 | 处理的数据 |", "|---------|------|-----------|"]
        for svc in self.config.third_party_services:
            parts.append(f"| {svc['name']} | {svc['purpose']} | {svc['data']} |")
        parts.append("\n> 各第三方服务均有独立的隐私政策，我们建议您阅读相关政策。")
        return "\n".join(parts)

    def _user_rights(self) -> str:
        rights = ["## 6. 您的权利\n\n", "根据相关法律法规，您享有以下权利：\n"]
        if self.config.supports_data_export:
            rights.append("- **数据导出权**: 您可以导出您的所有数据（JSON 格式）")
        if self.config.supports_data_deletion:
            rights.append("- **数据删除权**: 您可以删除特定识别记录或全部数据")
        if self.config.supports_account_deletion:
            rights.append("- **账户删除权**: 您可以永久删除您的账户及关联数据")
        rights.extend([
            "- **知情权**: 您有权了解我们如何处理您的数据",
            "- **更正权**: 您有权更正不准确的信息",
            "- **撤回同意权**: 您可以随时撤回对数据处理的同意",
            "\n> 行使权利请发送邮件至 " + self.config.contact_email,
        ])
        return "\n".join(rights)

    def _data_retention(self) -> str:
        return ("## 7. 数据保留\n\n"
                "- **本地识别记录**: 保留至您手动删除或卸载应用\n"
                "- **云端同步数据**: 账户删除后 30 天内永久清除\n"
                "- **崩溃日志**: 保留 90 天后自动删除\n"
                "- **使用统计**: 保留 12 个月后自动聚合匿名化")

    def _children_privacy(self) -> str:
        return ("## 8. 未成年人隐私\n\n"
                "本应用不面向 13 岁以下未成年人。我们不会故意收集未成年人的个人信息。"
                "如果您是未成年人，请在监护人指导下使用本应用。")

    def _policy_changes(self) -> str:
        return ("## 9. 政策变更\n\n"
                "我们可能不时更新本隐私政策。重大变更时，我们将通过应用内通知"
                "或邮件方式提前告知您。继续使用本应用即表示您同意更新后的政策。")

    def _contact(self) -> str:
        return (f"## 10. 联系我们\n\n"
                f"如有任何关于隐私政策的问题，请通过以下方式联系我们：\n\n"
                f"- **邮箱**: {self.config.contact_email}\n"
                f"- **运营方**: {self.config.company_name}\n"
                f"- **地址**: {self.config.company_address}")

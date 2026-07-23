"""
Firebase Crashlytics 崩溃监控配置

生成 Android (Gradle) 和 iOS (SPM/Podfile) 的 Crashlytics 集成配置，
并提供崩溃报告收集和分类接口。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CrashSeverity(Enum):
    """崩溃严重等级"""
    FATAL = "fatal"          # 致命崩溃（应用闪退）
    NON_FATAL = "non_fatal"   # 非致命异常（捕获的异常）
    ANR = "anr"               # Application Not Responding
    CUSTOM = "custom"          # 自定义关键事件


@dataclass
class CrashReport:
    """崩溃报告"""
    crash_id: str
    severity: CrashSeverity
    exception_type: str
    exception_message: str
    stack_trace: str
    device_model: str = ""
    os_version: str = ""
    app_version: str = ""
    user_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    custom_keys: dict = field(default_factory=dict)
    custom_logs: list = field(default_factory=list)


@dataclass
class CrashlyticsConfig:
    """Crashlytics 配置"""

    # Firebase 项目配置
    project_id: str = "minicpmv-app"
    android_app_id: str = "1:123456789012:android:abcdef123456"
    ios_app_id: str = "1:123456789012:ios:abcdef123456"
    api_key: str = "AIzaSyXXXXXXXXXXXXXXXXXXXXX"
    gcm_sender_id: str = "123456789012"

    # 采样与过滤
    sampling_rate: float = 1.0  # 1.0 = 100% 采样
    enable_anr: bool = True      # Android ANR 检测
    anr_timeout_seconds: int = 5
    enable_custom_logs: bool = True
    max_custom_logs: int = 64

    # 隐私设置
    enable_user_identifiers: bool = False  # GDPR 合规：不发送用户标识
    enable_device_identifiers: bool = False
    enable_crashlytics_opt_in: bool = True  # 需用户同意

    # 上传配置
    upload_symbols: bool = True  # 自动上传调试符号
    native_crash_reporting: bool = True

    def generate_android_gradle(self) -> str:
        """生成 Android Gradle Crashlytics 配置"""
        return f"""// android/app/build.gradle.kts - Crashlytics 配置

plugins {{
    id("com.google.firebase.crashlytics")
}}

android {{
    defaultConfig {{
        // Crashlytics 配置
        manifestPlaceholders["firebaseCrashlyticsCollectionEnabled"] = "false"  // 默认关闭，用户同意后开启
    }}

    buildTypes {{
        release {{
            // Release 构建自动上传符号
            firebaseCrashlytics {{
                nativeSymbolUploadEnabled = {str(self.upload_symbols).lower()}
                // 自动上传 NDK 符号
                unstrippedNativeLibsDir = "build/intermediates/merged_native_libs/release/out/lib"
            }}
        }}
    }}
}}

// Crashlytics 初始化配置
// 在 Application.onCreate() 中:
// FirebaseCrashlytics.getInstance().setCrashlyticsCollectionEnabled(userConsent)
// FirebaseCrashlytics.getInstance().setCustomKey("app_version", BuildConfig.VERSION_NAME)
"""

    def generate_ios_config(self) -> str:
        """生成 iOS Crashlytics 配置代码"""
        return f"""// iOS Crashlytics 配置

// Package.swift 依赖
// .package(url: "https://github.com/firebase/firebase-ios-sdk.git", from: "10.0.0")

// MiniCPMVApp.swift 中初始化
import FirebaseCore
import FirebaseCrashlytics

func configureCrashlytics() {{
    FirebaseApp.configure()

    let crashlytics = Crashlytics.crashlytics()
    // GDPR 合规：默认关闭，用户同意后开启
    crashlytics.isCrashlyticsCollectionEnabled = false

    // 设置自定义键
    crashlytics.setCustomValue("1.0.0", forKey: "app_version")
    crashlytics.setCustomValue(UIDevice.current.model, forKey: "device_model")
}}

// 用户同意后开启
func enableCrashlytics() {{
    Crashlytics.crashlytics().setCrashlyticsCollectionEnabled(true)
}}

// 记录自定义日志
func logCustomEvent(_ message: String) {{
    Crashlytics.crashlytics().log(message)
}}

// 记录非致命异常
func recordNonFatalError(_ error: Error, userInfo: [String: Any] = [:]) {{
    let exceptionModel = ExceptionModel(name: String(describing: type(of: error)),
                                         reason: error.localizedDescription)
    exceptionModel.stackTrace = Thread.callStackSymbols
        .map {{ StackFrame(symbol: $0) }}
    Crashlytics.crashlytics().record(exceptionModel: exceptionModel)
}}

// ANR 检测配置
// ANR 监测超时: {self.anr_timeout_seconds} 秒
// 通过 BGTaskScheduler 在后台检测主线程响应性
"""

    def generate_android_init_kotlin(self) -> str:
        """生成 Android Kotlin 初始化代码"""
        return f"""// MiniCPMVApplication.kt 中 Crashlytics 初始化

import com.google.firebase.crashlytics.FirebaseCrashlytics
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.analytics.ktx.analytics
import com.google.firebase.ktx.Firebase

fun initCrashlytics(userConsent: Boolean) {{
    val crashlytics = FirebaseCrashlytics.getInstance()

    // 用户同意后开启收集
    crashlytics.isCrashlyticsCollectionEnabled = userConsent

    // 设置自定义键
    crashlytics.setCustomKey("app_version", BuildConfig.VERSION_NAME)
    crashlytics.setCustomKey("device_model", android.os.Build.MODEL)
    crashlytics.setCustomKey("os_version", android.os.Build.VERSION.SDK_INT.toString())
    crashlytics.setCustomKey("model_version", "MiniCPM-V-4.6")

    // 设置用户标识（GDPR 合规：使用匿名 ID）
    if ({str(self.enable_user_identifiers).lower()}) {{
        crashlytics.setUserId(getAnonymousUserId())
    }}

    // 记录自定义日志
    crashlytics.log("App started - Crashlytics initialized")
}}

// 记录非致命异常
fun recordException(throwable: Throwable, context: String = "") {{
    val crashlytics = FirebaseCrashlytics.getInstance()
    if (context.isNotEmpty()) {{
        crashlytics.log(context)
    }}
    crashlytics.recordException(throwable)
}}

// ANR 检测
// 在 Application.onCreate 中:
// ANRWatchDog(timeoutInterval = {self.anr_timeout_seconds}s).start()
"""

    def process_crash(self, report: CrashReport) -> dict:
        """处理崩溃报告（模拟 Crashlytics 上传）"""
        processed = {
            "crash_id": report.crash_id,
            "severity": report.severity.value,
            "exception": {
                "type": report.exception_type,
                "message": report.exception_message,
                "stack_trace": report.stack_trace[:8192],  # 限制大小
            },
            "device": {
                "model": report.device_model,
                "os_version": report.os_version,
            },
            "app": {
                "version": report.app_version,
            },
            "timestamp": report.timestamp,
            "custom_keys": report.custom_keys if self.enable_user_identifiers else {},
            "logs": report.custom_logs[:self.max_custom_logs] if self.enable_custom_logs else [],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        return processed

    def get_dashboard_config(self) -> dict:
        """获取 Crashlytics 仪表板配置"""
        return {
            "project_id": self.project_id,
            "platforms": ["android", "ios"],
            "metrics": [
                "crash-free users (%)",
                "crash-free sessions (%)",
                "top crashes by impact",
                "crashes over time",
                "ANR rate (%)",
            ],
            "alerting": {
                "crash_rate_threshold": "0.1%",
                "anr_rate_threshold": "0.47%",
                "new_crash_alert": True,
                "regression_alert": True,
            },
            "target_slo": {
                "crash_free_users": ">= 99.9%",
                "crash_free_sessions": ">= 99.8%",
                "anr_rate": "< 0.47%",
            },
        }

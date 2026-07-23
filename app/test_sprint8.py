"""
Sprint 8 单元测试

覆盖：合规模块、监控模块、性能优化、发布管理
"""

import unittest
import json
import hashlib
from datetime import datetime

# 合规模块
from compliance.privacy_policy import PrivacyPolicyGenerator, PrivacyPolicyConfig
from compliance.data_compliance import (
    DataComplianceManager, DataExportRequest, DataDeletionRequest,
    ComplianceRequestStatus, ComplianceRequestType,
)
from compliance.store_checklist import (
    StoreChecklistValidator, CheckStatus, StoreType,
)

# 监控模块
from monitoring.crashlytics_config import CrashlyticsConfig, CrashReport, CrashSeverity
from monitoring.sentry_config import SentryConfig, SentryEventProcessor
from monitoring.metrics import MetricsCollector, MetricType
from monitoring.grafana_dashboard import GrafanaDashboardBuilder

# 性能优化
from performance.cold_start import ColdStartOptimizer, StartupPhase
from performance.memory_manager import MemoryManager, MemoryWarningLevel
from performance.battery_optimizer import BatteryOptimizer, PowerMode

# 发布管理
from release.gradual_rollout import (
    GradualRolloutManager, RolloutStage, RolloutConfig, RolloutMetrics,
)
from release.ab_test import ABTestManager, Variant, ExperimentStatus
from release.migration_plan import DatabaseMigrationPlan, MigrationPhase, MigrationStatus


class TestPrivacyPolicy(unittest.TestCase):
    """隐私政策生成器测试"""

    def setUp(self):
        self.config = PrivacyPolicyConfig()
        self.generator = PrivacyPolicyGenerator(self.config)

    def test_generate_markdown(self):
        md = self.generator.generate_markdown()
        self.assertIn("隐私政策", md)
        self.assertIn("MiniCPM-V", md)
        self.assertIn("收集的信息", md)
        self.assertIn("您的权利", md)

    def test_generate_html(self):
        html = self.generator.generate_html()
        self.assertIn("<html", html)
        self.assertIn("隐私政策", html)

    def test_generate_user_agreement(self):
        agreement = self.generator.generate_user_agreement()
        self.assertIn("用户协议", agreement)
        self.assertIn("服务描述", agreement)
        self.assertIn("免责声明", agreement)

    def test_third_party_services_in_policy(self):
        md = self.generator.generate_markdown()
        self.assertIn("Firebase Crashlytics", md)
        self.assertIn("阿里云 OSS", md)
        self.assertIn("通义千问", md)


class TestDataCompliance(unittest.TestCase):
    """数据合规管理器测试"""

    def setUp(self):
        self.manager = DataComplianceManager(":memory:")

    def test_data_export(self):
        request = DataExportRequest(
            request_id="export_001",
            user_id="user_123",
            export_format="json",
        )
        mock_data = {"records": [{"id": 1, "question": "test"}], "settings": {"theme": "dark"}}
        request = self.manager.process_data_export(
            request, lambda uid: mock_data
        )
        self.assertEqual(request.status, ComplianceRequestStatus.COMPLETED)
        self.assertEqual(request.exported_data, mock_data)
        self.assertIsNotNone(request.file_hash)
        self.assertIsNotNone(request.completed_at)

    def test_data_deletion(self):
        request = DataDeletionRequest(
            request_id="del_001",
            user_id="user_123",
            deletion_scope="all",
        )
        request = self.manager.process_data_deletion(
            request, lambda uid, scope: 42
        )
        self.assertEqual(request.status, ComplianceRequestStatus.COMPLETED)
        self.assertEqual(request.deleted_count, 42)
        self.assertIsNotNone(request.verification_hash)

    def test_encryption_audit(self):
        result = self.manager.run_encryption_audit()
        self.assertTrue(result.passed)
        self.assertGreater(len(result.items), 5)
        self.assertIn("local_database_encryption", [i["name"] for i in result.items])

    def test_compliance_report(self):
        # 先创建一些请求
        self.test_data_export()
        self.test_data_deletion()
        report = self.manager.get_compliance_report()
        self.assertIn("summary", report)
        self.assertIn("recent_requests", report)
        self.assertGreater(len(report["recent_requests"]), 0)


class TestStoreChecklist(unittest.TestCase):
    """商店合规清单测试"""

    def setUp(self):
        self.validator = StoreChecklistValidator()

    def test_initial_state_all_fail(self):
        report = self.validator.get_report()
        self.assertGreater(report["failed"], 0)
        self.assertFalse(report["ready_for_submission"])

    def test_check_pass(self):
        self.validator.check("privacy_policy_url", CheckStatus.PASS, "https://example.com/privacy")
        report = self.validator.get_report()
        self.assertGreater(report["passed"], 0)

    def test_validate_all(self):
        checks = {
            "privacy_policy_url": (CheckStatus.PASS, "已部署"),
            "camera_justification": (CheckStatus.PASS, "AI 视觉识别需要"),
            "data_encryption": (CheckStatus.PASS, "SQLCipher AES-256"),
            "target_sdk": (CheckStatus.PASS, "targetSdk 34"),
            "app_icon_512": (CheckStatus.PASS, "icon_512.png"),
        }
        fail_count = self.validator.validate_all(checks)
        self.assertLess(fail_count, self.validator.get_fail_count() + len(checks))

    def test_google_play_filter(self):
        report = self.validator.get_report(StoreType.GOOGLE_PLAY)
        self.assertGreater(report["total_items"], 10)

    def test_app_store_filter(self):
        report = self.validator.get_report(StoreType.APP_STORE)
        self.assertGreater(report["total_items"], 10)

    def test_markdown_output(self):
        md = self.validator.get_checklist_markdown()
        self.assertIn("合规清单", md)


class TestCrashlyticsConfig(unittest.TestCase):
    """Crashlytics 配置测试"""

    def setUp(self):
        self.config = CrashlyticsConfig()

    def test_generate_android_gradle(self):
        gradle = self.config.generate_android_gradle()
        self.assertIn("firebase.crashlytics", gradle)
        self.assertIn("nativeSymbolUploadEnabled", gradle)

    def test_generate_ios_config(self):
        ios = self.config.generate_ios_config()
        self.assertIn("FirebaseApp.configure", ios)
        self.assertIn("Crashlytics.crashlytics()", ios)

    def test_generate_android_kotlin(self):
        kotlin = self.config.generate_android_init_kotlin()
        self.assertIn("FirebaseCrashlytics", kotlin)
        self.assertIn("isCrashlyticsCollectionEnabled", kotlin)

    def test_process_crash(self):
        report = CrashReport(
            crash_id="crash_001",
            severity=CrashSeverity.FATAL,
            exception_type="NullPointerException",
            exception_message="cameraManager is null",
            stack_trace="at com.minicpmv.app.CameraManager...",
            device_model="Pixel 8",
            os_version="Android 14",
            app_version="1.0.0",
        )
        processed = self.config.process_crash(report)
        self.assertEqual(processed["severity"], "fatal")
        self.assertEqual(processed["exception"]["type"], "NullPointerException")

    def test_dashboard_config(self):
        dashboard = self.config.get_dashboard_config()
        self.assertIn("crash-free users (%)", dashboard["metrics"])
        self.assertIn("target_slo", dashboard)


class TestSentryConfig(unittest.TestCase):
    """Sentry 配置测试"""

    def setUp(self):
        self.config = SentryConfig()

    def test_generate_python_init(self):
        code = self.config.generate_python_init()
        self.assertIn("sentry_sdk.init", code)
        self.assertIn("FastApiIntegration", code)
        self.assertIn("filter_sensitive_data", code)

    def test_generate_android_init(self):
        code = self.config.generate_android_init()
        self.assertIn("SentryAndroid.init", code)
        self.assertIn("tracesSampleRate", code)

    def test_generate_ios_init(self):
        code = self.config.generate_ios_init()
        self.assertIn("SentrySDK.start", code)
        self.assertIn("options.dsn", code)

    def test_performance_config(self):
        perf = self.config.get_performance_config()
        self.assertTrue(perf["tracing"]["enabled"])
        self.assertGreater(perf["tracing"]["sample_rate"], 0)

    def test_event_processor_sanitize(self):
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer token123",
                    "Content-Type": "application/json",
                },
                "data": {
                    "password": "secret123",
                    "username": "test_user",
                    "nested": {"token": "abc"},
                },
            },
            "extra": {"session_id": "xyz"},
        }
        sanitized = SentryEventProcessor.sanitize_event(event)
        self.assertEqual(sanitized["request"]["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(sanitized["request"]["data"]["password"], "[REDACTED]")
        self.assertEqual(sanitized["request"]["data"]["nested"]["token"], "[REDACTED]")
        self.assertEqual(sanitized["extra"]["session_id"], "[REDACTED]")
        # 非敏感字段保留
        self.assertEqual(sanitized["request"]["headers"]["Content-Type"], "application/json")
        self.assertEqual(sanitized["request"]["data"]["username"], "test_user")

    def test_event_processor_ignore(self):
        event = {
            "exception": {
                "values": [{"type": "NetworkError", "message": "timeout"}],
            },
        }
        self.assertTrue(SentryEventProcessor.should_ignore(event, ["NetworkError"]))


class TestMetricsCollector(unittest.TestCase):
    """Prometheus 指标采集器测试"""

    def setUp(self):
        self.collector = MetricsCollector()

    def test_increment_counter(self):
        self.collector.increment("http_requests_total", labels={"method": "GET"})
        self.collector.increment("http_requests_total", labels={"method": "GET"})
        summary = self.collector.get_summary()
        self.assertGreater(summary["total_counters"], 0)

    def test_set_gauge(self):
        self.collector.set_gauge("db_connections_active", 5)
        self.collector.set_gauge("db_connections_active", 8)
        summary = self.collector.get_summary()
        self.assertGreater(summary["total_gauges"], 0)

    def test_observe_histogram(self):
        for v in [0.1, 0.2, 0.3, 0.5, 1.0]:
            self.collector.observe("inference_duration_seconds", v)
        summary = self.collector.get_summary()
        self.assertGreater(summary["total_histograms"], 0)

    def test_observe_inference(self):
        self.collector.observe_inference(
            duration=0.5, confidence=0.92, cached=True, success=True, source="local"
        )
        self.collector.observe_inference(
            duration=1.2, confidence=0.85, cached=False, success=False, source="cloud"
        )
        prom = self.collector.export_prometheus()
        self.assertIn("inference_requests_total", prom)
        self.assertIn("inference_duration_seconds", prom)

    def test_observe_cloud_call(self):
        self.collector.observe_cloud_call("qwen", 0.8, True)
        self.collector.observe_cloud_call("doubao", 1.5, False)
        prom = self.collector.export_prometheus()
        self.assertIn("cloud_api_calls_total", prom)
        self.assertIn("provider", prom)

    def test_export_prometheus_format(self):
        self.collector.increment("http_requests_total", labels={"method": "POST", "status": "200"})
        prom = self.collector.export_prometheus()
        self.assertIn("# HELP", prom)
        self.assertIn("# TYPE", prom)
        self.assertIn("http_requests_total", prom)


class TestGrafanaDashboard(unittest.TestCase):
    """Grafana 仪表板构建器测试"""

    def setUp(self):
        self.builder = GrafanaDashboardBuilder()

    def test_build_dashboard(self):
        dashboard = self.builder.build()
        self.assertEqual(dashboard["title"], "MiniCPM-V 端侧视觉助手 - 监控仪表板")
        self.assertGreater(len(dashboard["panels"]), 8)
        self.assertEqual(dashboard["refresh"], "10s")

    def test_to_json(self):
        json_str = self.builder.to_json()
        data = json.loads(json_str)
        self.assertIn("panels", data)
        self.assertIn("templating", data)

    def test_alert_rules(self):
        rules = self.builder.get_alert_rules()
        self.assertGreater(len(rules), 3)
        rule_names = [r["name"] for r in rules]
        self.assertIn("推理错误率过高", rule_names)
        self.assertIn("P95 延迟过高", rule_names)

    def test_panel_types(self):
        dashboard = self.builder.build()
        panel_types = [p["type"] for p in dashboard["panels"]]
        self.assertIn("stat", panel_types)
        self.assertIn("timeseries", panel_types)


class TestColdStartOptimizer(unittest.TestCase):
    """冷启动优化器测试"""

    def setUp(self):
        self.optimizer = ColdStartOptimizer(target_ms=2000.0)

    def test_simulate_startup(self):
        profile = self.optimizer.simulate_startup()
        self.assertGreater(profile.total_duration_ms, 0)
        self.assertIn(StartupPhase.APP_CREATE.value, profile.phases)
        self.assertIn(StartupPhase.IDLE.value, profile.phases)

    def test_meets_target(self):
        profile = self.optimizer.simulate_startup()
        # 同步阶段应该在目标范围内
        self.assertLess(profile.total_duration_ms, 2000.0)

    def test_generate_android_config(self):
        config = self.optimizer.generate_android_config()
        self.assertIn("MiniCPMVApplication", config)
        self.assertIn("IdleHandler", config)

    def test_generate_ios_config(self):
        config = self.optimizer.generate_ios_config()
        self.assertIn("MiniCPMVApp", config)
        self.assertIn("task {", config)

    def test_optimization_report(self):
        report = self.optimizer.get_optimization_report()
        self.assertIn("total_duration_ms", report)
        self.assertIn("recommendations", report)
        self.assertIn("bottleneck", report)

    def test_bottleneck_identification(self):
        profile = self.optimizer.simulate_startup()
        bottleneck = profile.get_bottleneck()
        self.assertIsNotNone(bottleneck)


class TestMemoryManager(unittest.TestCase):
    """内存管理器测试"""

    def setUp(self):
        self.manager = MemoryManager(max_cache_size=5, max_cache_memory_mb=1.0)

    def test_cache_inference_result(self):
        for i in range(10):
            self.manager.cache_inference_result(f"key_{i}", {"result": f"answer_{i}"}, size_kb=10)
        # 超过 max_cache_size=5，应该只保留最近 5 个
        self.assertLessEqual(len(self.manager._inference_cache), 5)

    def test_cache_hit(self):
        self.manager.cache_inference_result("test_key", {"answer": "42"})
        result = self.manager.get_cached_inference("test_key")
        self.assertEqual(result["answer"], "42")

    def test_cache_miss(self):
        result = self.manager.get_cached_inference("nonexistent")
        self.assertIsNone(result)

    def test_memory_warning_warning(self):
        warning = self.manager.handle_memory_warning(used_mb=600, total_mb=800)
        self.assertEqual(warning.level, MemoryWarningLevel.WARNING)

    def test_memory_warning_critical(self):
        warning = self.manager.handle_memory_warning(used_mb=700, total_mb=800)
        self.assertEqual(warning.level, MemoryWarningLevel.CRITICAL)

    def test_memory_warning_emergency(self):
        # 先缓存一些数据
        self.manager.cache_inference_result("key1", {"data": "1"})
        self.manager.cache_image("img1", b"x" * 1024)
        warning = self.manager.handle_memory_warning(used_mb=780, total_mb=800)
        self.assertEqual(warning.level, MemoryWarningLevel.EMERGENCY)
        # 紧急模式应清空所有缓存
        self.assertEqual(len(self.manager._inference_cache), 0)
        self.assertEqual(len(self.manager._image_cache), 0)

    def test_memory_stats(self):
        self.manager.cache_inference_result("k1", {"v": 1})
        stats = self.manager.get_memory_stats()
        self.assertEqual(stats["inference_cache"]["entries"], 1)
        self.assertEqual(stats["current_level"], "normal")

    def test_image_optimization_config(self):
        config = MemoryManager.get_image_optimization_config()
        self.assertEqual(config["shared"]["max_image_dimension"], 448)
        self.assertIn("android", config)
        self.assertIn("ios", config)


class TestBatteryOptimizer(unittest.TestCase):
    """电池优化器测试"""

    def setUp(self):
        self.optimizer = BatteryOptimizer()

    def test_high_battery_charging(self):
        mode = self.optimizer.update_power_state(80, is_charging=True)
        self.assertEqual(mode, PowerMode.PERFORMANCE)

    def test_normal_battery(self):
        mode = self.optimizer.update_power_state(40, is_charging=False)
        self.assertEqual(mode, PowerMode.BALANCED)

    def test_low_battery(self):
        mode = self.optimizer.update_power_state(15, is_charging=False)
        self.assertEqual(mode, PowerMode.LOW_POWER)

    def test_ultra_low_battery(self):
        mode = self.optimizer.update_power_state(5, is_charging=False)
        self.assertEqual(mode, PowerMode.ULTRA_LOW)

    def test_power_saver_mode(self):
        mode = self.optimizer.update_power_state(50, is_charging=False, is_power_saver=True)
        self.assertEqual(mode, PowerMode.ULTRA_LOW)

    def test_schedule_changes_with_mode(self):
        # 高性能模式
        self.optimizer.update_power_state(90, is_charging=True)
        schedule = self.optimizer.get_current_schedule()
        self.assertEqual(schedule.model_precision, "fp16")
        self.assertTrue(schedule.enable_background_recognition)

        # 超低电量
        self.optimizer.update_power_state(5, is_charging=False)
        schedule = self.optimizer.get_current_schedule()
        self.assertEqual(schedule.model_precision, "int4")
        self.assertFalse(schedule.enable_background_recognition)

    def test_should_allow_inference(self):
        self.optimizer.update_power_state(90, is_charging=True)
        schedule = self.optimizer.get_current_schedule()
        self.assertTrue(self.optimizer.should_allow_inference(0))
        self.assertTrue(self.optimizer.should_allow_inference(schedule.max_inference_per_session - 1))
        self.assertFalse(self.optimizer.should_allow_inference(schedule.max_inference_per_session))

    def test_work_scheduler_config(self):
        self.optimizer.update_power_state(15, is_charging=False)
        config = self.optimizer.get_work_scheduler_config()
        self.assertIn("android", config)
        self.assertIn("ios", config)

    def test_doze_mode_config(self):
        config = BatteryOptimizer.get_doze_mode_config()
        self.assertTrue(config["strategy"]["use_workmanager_expedited"])

    def test_battery_report(self):
        self.optimizer.update_power_state(30, is_charging=False)
        report = self.optimizer.get_battery_report()
        self.assertIn("current_mode", report)
        self.assertIn("estimated_battery_savings", report)


class TestGradualRollout(unittest.TestCase):
    """灰度发布管理器测试"""

    def setUp(self):
        self.config = RolloutConfig(stage=RolloutStage.INTERNAL_TEST, rollout_percentage=1.0)
        self.manager = GradualRolloutManager(self.config)

    def test_user_bucketing_1_percent(self):
        # 1% 灰度，大约 1% 的用户应该收到更新
        update_count = 0
        total_users = 10000
        for i in range(total_users):
            if self.manager.should_user_get_update(f"user_{i}"):
                update_count += 1
        ratio = update_count / total_users
        self.assertLess(ratio, 0.03)  # 应该接近 1%

    def test_user_bucketing_100_percent(self):
        self.config.stage = RolloutStage.FULL_RELEASE
        self.config.rollout_percentage = 100.0
        self.assertTrue(self.manager.should_user_get_update("any_user"))

    def test_user_bucketing_paused(self):
        self.config.stage = RolloutStage.PAUSED
        self.assertFalse(self.manager.should_user_get_update("any_user"))

    def test_advance_stage(self):
        self.assertEqual(self.manager.config.stage, RolloutStage.INTERNAL_TEST)
        self.manager.advance_stage()
        self.assertEqual(self.manager.config.stage, RolloutStage.ALPHA)
        self.assertAlmostEqual(self.manager.config.rollout_percentage, 5.0)

    def test_full_advancement(self):
        stages = [RolloutStage.INTERNAL_TEST, RolloutStage.ALPHA, RolloutStage.BETA,
                  RolloutStage.PRODUCTION_50, RolloutStage.FULL_RELEASE]
        for expected in stages[1:]:
            self.manager.advance_stage()
            self.assertEqual(self.manager.config.stage, expected)

    def test_pause_and_rollback(self):
        self.manager.pause_rollout("发现崩溃")
        self.assertEqual(self.manager.config.stage, RolloutStage.PAUSED)
        self.manager.config.stage = RolloutStage.BETA  # 恢复用于测试
        self.manager.rollback("崩溃严重")
        self.assertEqual(self.manager.config.stage, RolloutStage.ROLLED_BACK)

    def test_health_check_healthy(self):
        metrics = RolloutMetrics(
            active_users=1000, crash_rate=0.1, anr_rate=0.2,
            api_error_rate=2.0, negative_feedback_count=5, total_feedback_count=100,
        )
        result = self.manager.update_metrics(metrics)
        self.assertTrue(result["healthy"])

    def test_health_check_unhealthy(self):
        metrics = RolloutMetrics(
            active_users=1000, crash_rate=1.0, anr_rate=0.2,
            api_error_rate=2.0, negative_feedback_count=5, total_feedback_count=100,
        )
        result = self.manager.update_metrics(metrics)
        self.assertFalse(result["healthy"])
        self.assertEqual(result["action"], "auto_rollback")

    def test_store_rollout_config(self):
        config = self.manager.get_store_rollout_config()
        self.assertIn("google_play", config)
        self.assertIn("app_store", config)


class TestABTestManager(unittest.TestCase):
    """A/B 测试管理器测试"""

    def setUp(self):
        self.manager = ABTestManager()

    def test_create_experiment(self):
        exp = self.manager.create_experiment(
            experiment_id="exp_001",
            name="推理引擎对比",
            variants=[
                Variant(name="control", description="ONNX Runtime", weight=50),
                Variant(name="treatment", description="Core ML", weight=50),
            ],
        )
        self.assertEqual(len(exp.variants), 2)
        self.assertEqual(exp.status, ExperimentStatus.DRAFT)

    def test_variant_assignment(self):
        self.manager.create_experiment(
            "exp_002", "UI 测试",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
        )
        self.manager.start_experiment("exp_002")
        variant = self.manager.get_variant_for_user("exp_002", "user_123")
        self.assertIn(variant, ["control", "treatment"])

    def test_deterministic_assignment(self):
        self.manager.create_experiment(
            "exp_003", "确定性测试",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
        )
        self.manager.start_experiment("exp_003")
        v1 = self.manager.get_variant_for_user("exp_003", "user_abc")
        v2 = self.manager.get_variant_for_user("exp_003", "user_abc")
        self.assertEqual(v1, v2)

    def test_record_conversion(self):
        self.manager.create_experiment(
            "exp_004", "转化测试",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
        )
        self.manager.start_experiment("exp_004")
        variant = self.manager.get_variant_for_user("exp_004", "user_001")
        self.manager.record_conversion("exp_004", variant, "latency_ms", 500.0)
        exp = self.manager._experiments["exp_004"]
        self.assertEqual(exp.variants[variant].conversions, 1)

    def test_analyze_significant(self):
        exp = self.manager.create_experiment(
            "exp_005", "显著性测试",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
            min_sample_size=10,
        )
        self.manager.start_experiment("exp_005")

        # 模拟大量数据：treatment 明显更好
        for i in range(500):
            v_ctrl = exp.assign_variant(f"user_{i}")
            if v_ctrl == "control":
                if i % 2 == 0:  # 50% 转化
                    exp.variants["control"].conversions += 1
            else:
                if i % 3 != 0:  # 67% 转化
                    exp.variants["treatment"].conversions += 1

        result = self.manager.analyze_experiment("exp_005")
        self.assertTrue(result.is_significant)
        self.assertEqual(result.winner, "treatment")

    def test_analyze_insufficient_sample(self):
        self.manager.create_experiment(
            "exp_006", "样本不足",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
            min_sample_size=10000,
        )
        self.manager.start_experiment("exp_006")
        self.manager.get_variant_for_user("exp_006", "user_1")
        result = self.manager.analyze_experiment("exp_006")
        self.assertIn("样本量不足", result.recommendation)

    def test_experiment_summary(self):
        self.manager.create_experiment(
            "exp_007", "摘要测试",
            [Variant(name="control", weight=50), Variant(name="treatment", weight=50)],
        )
        summary = self.manager.get_experiment_summary()
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["id"], "exp_007")

    def test_z_test(self):
        # 明显差异
        self.assertTrue(ABTestManager._z_test(1000, 500, 1000, 600, 0.05))
        # 无差异
        self.assertFalse(ABTestManager._z_test(1000, 500, 1000, 501, 0.05))


class TestDatabaseMigrationPlan(unittest.TestCase):
    """数据库迁移方案测试"""

    def setUp(self):
        self.plan = DatabaseMigrationPlan()

    def test_initial_state(self):
        self.assertEqual(self.plan._current_phase, MigrationPhase.PREPARATION)
        self.assertFalse(self.plan._dual_write_enabled)
        self.assertEqual(self.plan._read_source, "sqlite")

    def test_execute_preparation_steps(self):
        step = self.plan.execute_step("create_pg_schema", lambda: 0)
        self.assertEqual(step.status, MigrationStatus.SUCCESS)

        step = self.plan.execute_step("validate_schema", lambda: 0)
        self.assertEqual(step.status, MigrationStatus.SUCCESS)

        step = self.plan.execute_step("bulk_import", lambda: 1000)
        self.assertEqual(step.status, MigrationStatus.SUCCESS)
        self.assertEqual(step.records_migrated, 1000)

    def test_enable_dual_write(self):
        # 先完成准备阶段
        self.plan.execute_step("create_pg_schema")
        self.plan.execute_step("validate_schema")
        self.plan.execute_step("bulk_import", lambda: 500)

        # 开启双写
        self.plan.execute_step("enable_dual_write")
        self.assertTrue(self.plan._dual_write_enabled)

        config = self.plan.get_dual_write_config()
        self.assertTrue(config["enabled"])
        self.assertIn("sqlite", config["write_targets"])
        self.assertIn("postgresql", config["write_targets"])

    def test_read_switch(self):
        # 完成前面所有步骤
        for step_name in ["create_pg_schema", "validate_schema", "bulk_import",
                          "enable_dual_write", "monitor_dual_write",
                          "data_consistency_check", "incremental_sync"]:
            self.plan.execute_step(step_name, lambda: 100)

        self.plan.execute_step("switch_read_to_pg")
        self.assertEqual(self.plan._read_source, "postgresql")

    def test_rollback(self):
        self.plan.execute_step("enable_dual_write")
        self.assertTrue(self.plan._dual_write_enabled)
        self.plan.rollback("测试回滚")
        self.assertEqual(self.plan._current_phase, MigrationPhase.ROLLED_BACK)
        self.assertFalse(self.plan._dual_write_enabled)
        self.assertEqual(self.plan._read_source, "sqlite")

    def test_step_failure(self):
        def failing_callback():
            raise Exception("连接 PostgreSQL 失败")

        step = self.plan.execute_step("create_pg_schema", failing_callback)
        self.assertEqual(step.status, MigrationStatus.FAILED)
        self.assertIn("连接 PostgreSQL 失败", step.error)

    def test_migration_progress(self):
        self.plan.execute_step("create_pg_schema")
        progress = self.plan.get_migration_progress()
        self.assertEqual(progress["completed"], 1)
        self.assertGreater(progress["progress_pct"], 0)
        self.assertEqual(len(progress["steps"]), 11)

    def test_generate_runbook(self):
        runbook = self.plan.generate_runbook()
        self.assertIn("数据库迁移", runbook)
        self.assertIn("双写", runbook)
        self.assertIn("回滚", runbook)
        self.assertIn("时间线", runbook)


if __name__ == "__main__":
    unittest.main(verbosity=2)

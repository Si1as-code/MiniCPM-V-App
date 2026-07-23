"""
冷启动优化

通过分阶段延迟初始化、预加载策略和启动时间分析，
将应用冷启动时间控制在目标范围内。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class StartupPhase(Enum):
    """启动阶段"""
    PRE_CREATE = "pre_create"      # Application.onCreate 之前
    APP_CREATE = "app_create"       # Application.onCreate
    POST_CREATE = "post_create"     # Application.onCreate 之后
    FIRST_FRAME = "first_frame"     # 第一帧渲染
    IDLE = "idle"                    # 空闲后预加载


@dataclass
class StartupTask:
    """启动任务"""
    name: str
    phase: StartupPhase
    priority: int = 0  # 越小越优先
    callback: Optional[Callable] = None
    duration_ms: float = 0.0
    is_async: bool = False
    is_required: bool = True  # 是否必须完成才能继续


@dataclass
class StartupProfile:
    """启动性能记录"""
    total_duration_ms: float = 0.0
    phases: dict = field(default_factory=dict)
    tasks: list = field(default_factory=list)
    target_ms: float = 2000.0  # 目标冷启动 2 秒

    @property
    def meets_target(self) -> bool:
        return self.total_duration_ms <= self.target_ms

    def get_bottleneck(self) -> Optional[str]:
        """获取最耗时的任务"""
        if not self.tasks:
            return None
        return max(self.tasks, key=lambda t: t["duration_ms"])["name"]


class ColdStartOptimizer:
    """冷启动优化器"""

    def __init__(self, target_ms: float = 2000.0):
        self.target_ms = target_ms
        self._tasks: dict[StartupPhase, list[StartupTask]] = {
            phase: [] for phase in StartupPhase
        }
        self._init_default_tasks()

    def _init_default_tasks(self):
        """初始化默认启动任务"""
        # ===== PRE_CREATE: 系统级，无法控制 =====
        # 预估 200ms

        # ===== APP_CREATE: 必须同步完成的关键初始化 =====
        self.register_task(StartupTask(
            name="load_settings", phase=StartupPhase.APP_CREATE,
            priority=0, is_required=True, duration_ms=15,
        ))
        self.register_task(StartupTask(
            name="init_crashlytics", phase=StartupPhase.APP_CREATE,
            priority=0, is_required=True, duration_ms=30,
        ))
        self.register_task(StartupTask(
            name="init_database", phase=StartupPhase.APP_CREATE,
            priority=1, is_required=True, duration_ms=80,
        ))

        # ===== POST_CREATE: 可延迟的非关键初始化 =====
        self.register_task(StartupTask(
            name="init_sentry", phase=StartupPhase.POST_CREATE,
            priority=2, is_async=True, is_required=False, duration_ms=50,
        ))
        self.register_task(StartupTask(
            name="init_network_client", phase=StartupPhase.POST_CREATE,
            priority=1, is_async=True, duration_ms=40,
        ))
        self.register_task(StartupTask(
            name="init_camera_manager", phase=StartupPhase.POST_CREATE,
            priority=2, is_async=True, duration_ms=100,
        ))

        # ===== FIRST_FRAME: UI 首帧渲染 =====
        self.register_task(StartupTask(
            name="render_first_frame", phase=StartupPhase.FIRST_FRAME,
            priority=0, is_required=True, duration_ms=120,
        ))

        # ===== IDLE: 空闲后预加载（不阻塞启动） =====
        self.register_task(StartupTask(
            name="warmup_inference_engine", phase=StartupPhase.IDLE,
            priority=0, is_async=True, is_required=False, duration_ms=1500,
        ))
        self.register_task(StartupTask(
            name="prefetch_user_data", phase=StartupPhase.IDLE,
            priority=1, is_async=True, is_required=False, duration_ms=200,
        ))
        self.register_task(StartupTask(
            name="register_bg_tasks", phase=StartupPhase.IDLE,
            priority=2, is_async=True, is_required=False, duration_ms=30,
        ))

    def register_task(self, task: StartupTask):
        """注册启动任务"""
        self._tasks[task.phase].append(task)
        # 按优先级排序
        self._tasks[task.phase].sort(key=lambda t: t.priority)

    def simulate_startup(self) -> StartupProfile:
        """模拟启动过程，返回性能记录"""
        profile = StartupProfile(target_ms=self.target_ms)
        total_ms = 200.0  # PRE_CREATE 预估

        profile.phases[StartupPhase.PRE_CREATE.value] = {"duration_ms": total_ms, "tasks": []}

        for phase in [StartupPhase.APP_CREATE, StartupPhase.POST_CREATE,
                       StartupPhase.FIRST_FRAME]:
            phase_duration = 0.0
            phase_tasks = []

            for task in self._tasks[phase]:
                # 同步任务计入启动时间，异步任务不计入
                effective_duration = task.duration_ms if not task.is_async else 0
                if phase == StartupPhase.APP_CREATE:
                    # APP_CREATE 阶段所有任务都阻塞
                    effective_duration = task.duration_ms

                phase_duration += effective_duration
                phase_tasks.append({
                    "name": task.name,
                    "duration_ms": task.duration_ms,
                    "async": task.is_async,
                    "effective_ms": effective_duration,
                })

            total_ms += phase_duration
            profile.phases[phase.value] = {
                "duration_ms": phase_duration,
                "tasks": phase_tasks,
            }
            profile.tasks.extend(phase_tasks)

        # IDLE 阶段不计入启动时间
        idle_tasks = []
        idle_duration = 0.0
        for task in self._tasks[StartupPhase.IDLE]:
            idle_duration += task.duration_ms
            idle_tasks.append({
                "name": task.name,
                "duration_ms": task.duration_ms,
                "async": task.is_async,
            })
        profile.phases[StartupPhase.IDLE.value] = {
            "duration_ms": idle_duration,
            "tasks": idle_tasks,
            "note": "不计入冷启动时间",
        }

        profile.total_duration_ms = total_ms
        return profile

    def generate_android_config(self) -> str:
        """生成 Android 冷启动优化配置"""
        return """// Android 冷启动优化

// 1. MiniCPMVApplication.kt - 使用 App Startup 库
// build.gradle.kts: implementation("androidx.startup:startup-runtime:1.1.1")

// 2. 延迟初始化策略
class MiniCPMVApplication : Application() {
    override fun onCreate() {
        super.onCreate()

        // === 同步初始化（必须） ===
        // 1. 加载用户设置 (~15ms)
        initSettings()

        // 2. 初始化 Crashlytics (~30ms)
        initCrashlytics()

        // 3. 初始化数据库 (~80ms)  ← 最耗时
        initDatabase()

        // === 异步初始化（后台线程） ===
        CoroutineScope(Dispatchers.IO).launch {
            // 4. 初始化 Sentry (~50ms, 后台)
            initSentry()
            // 5. 初始化网络客户端 (~40ms, 后台)
            initNetworkClient()
            // 6. 初始化相机管理 (~100ms, 后台)
            initCameraManager()
        }

        // === 空闲后预加载 ===
        // 使用 IdleHandler 在主线程空闲时执行
        Looper.myQueue().addIdleHandler {
            CoroutineScope(Dispatchers.IO).launch {
                // 7. 预热推理引擎 (~1500ms, 后台)
                warmupInferenceEngine()
                // 8. 预取用户数据 (~200ms, 后台)
                prefetchUserData()
                // 9. 注册后台任务 (~30ms, 后台)
                registerBackgroundTasks()
            }
            false  // 只执行一次
        }
    }
}

// 3. 使用 SplashScreen API
// themes.xml:
// <style name="Theme.MiniCPMV.Splash" parent="Theme.SplashScreen">
//     <item name="windowSplashScreenBackground">@color/primary_blue</item>
//     <item name="windowSplashScreenAnimatedIcon">@drawable/ic_logo</item>
//     <item name="postSplashScreenTheme">@style/Theme.MiniCPMV</item>
// </style>
"""

    def generate_ios_config(self) -> str:
        """生成 iOS 冷启动优化配置"""
        return """// iOS 冷启动优化

// MiniCPMVApp.swift
struct MiniCPMVApp: App {
    @StateObject private var appState = AppState()

    init() {
        // === 同步初始化（必须） ===
        // 1. 加载设置 (~15ms)
        // 2. 初始化 Crashlytics (~30ms)
        configureCrashlytics()
        // 3. 初始化 Core Data (~80ms)
        _ = CoreDataStack.shared

        // === 异步初始化 ===
        // 在 first appear 后异步执行
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .task {
                    // 后台异步初始化
                    await initializeAsync()
                }
        }
    }

    func initializeAsync() async {
        // 4. 初始化 Sentry (~50ms)
        initSentry()
        // 5. 初始化网络客户端 (~40ms)
        _ = APIClient.shared
        // 6. 初始化相机 (~100ms)

        // === 空闲后预加载 ===
        await Task.yield()  // 让 UI 先渲染

        // 7. 预热推理引擎 (~1500ms)
        await appState.inferenceEngine.warmup()
        // 8. 预取数据 (~200ms)
        await prefetchUserData()
        // 9. 注册后台任务 (~30ms)
        BackgroundTaskScheduler.shared.registerTasks()
    }
}

// 优化要点：
// - UIApplicationDelegate 不做耗时操作
// - 最小化 init() 中的同步操作
// - 使用 .task 修饰符在首个视图 appear 后异步初始化
// - 推理引擎预热放在 Task.yield() 之后，确保首帧先渲染
"""

    def get_optimization_report(self) -> dict:
        """获取优化报告"""
        profile = self.simulate_startup()
        return {
            "total_duration_ms": profile.total_duration_ms,
            "target_ms": self.target_ms,
            "meets_target": profile.meets_target,
            "bottleneck": profile.get_bottleneck(),
            "phases": profile.phases,
            "recommendations": self._get_recommendations(profile),
        }

    def _get_recommendations(self, profile: StartupProfile) -> list:
        """根据启动记录生成优化建议"""
        recs = []
        if not profile.meets_target:
            recs.append(f"冷启动 {profile.total_duration_ms:.0f}ms 超过目标 {profile.target_ms:.0f}ms")

            # 分析各阶段
            app_create = profile.phases.get(StartupPhase.APP_CREATE.value, {})
            if app_create.get("duration_ms", 0) > 200:
                recs.append("APP_CREATE 阶段耗时过长，考虑将数据库初始化移至后台线程")

            bottleneck = profile.get_bottleneck()
            if bottleneck:
                recs.append(f"最耗时任务: {bottleneck}，考虑延迟到 IDLE 阶段")

        # 检查是否有同步任务可以改为异步
        for task_info in profile.tasks:
            if not task_info.get("async", False) and not task_info.get("is_required", True):
                recs.append(f"任务 '{task_info['name']}' 可改为异步执行")

        if not recs:
            recs.append("冷启动性能达标，当前配置良好")
        return recs

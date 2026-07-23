# MiniCPM-V 端侧视觉助手

基于 [MiniCPM-V 4.6](https://github.com/OpenBMB/MiniCPM-V) 构建的产业级移动端视觉理解 App，实现端侧实时拍照识别、多轮问答、后台常驻任务与云端 API 协同。

## 当前完成状态

### Sprint 0: 项目初始化 ✅
- 官方仓库分析（9 个历史版本）
- 架构设计（4 层架构、6 张数据库表）
- AutoDL GPU 环境配置
- SSH 免密登录 + 本地→云端代码同步

### Sprint 1: 端侧推理引擎 ✅
- MiniCPM-V 4.6 模型加载与推理
- ModelScope 国内源下载（免登录）
- LRU 缓存（244x 加速）
- 线程安全单例模式
- 模型预热（减少首次推理延迟）

**测试结果**: 加载 5.8s | 推理 2.3s | 显存 2.5GB | 缓存命中 0.01s

### Sprint 2: 数据持久层 ✅
- SQLite 本地数据库（WAL 模式，6 张表）
- 识别记录 DAO（hash 查询、同步标记、统计）
- 多轮对话 DAO（外键关联、token 统计）
- API 任务队列 DAO（状态管理、重试）
- 用户设置 DAO（JSON 序列化、类型快捷方法）
- 使用统计 DAO（日聚合、预算检查）
- SAVEPOINT 嵌套事务（原子性保障）

**测试结果**: 7 项单元测试全部通过（含事务回滚验证）

### Sprint 3: API 调度引擎 ✅
- 端云协同路由引擎（`SchedulerRouter.schedule()`）
- 5 步决策流程：任务类型 → 预算 → 端侧 → 云端 → 降级
- 预算控制（`BudgetController`，与 `settings_dao`/`usage_dao` 联动）
- 云端 Provider 插件化架构（`BaseProvider` 基类）
- Qwen-VL-Plus 适配（通义千问，DashScope HTTP API）
- 豆包视觉 Pro 适配（火山引擎 Ark HTTP API）
- 降级策略（云端失败 → 端侧重试，详细 prompt）
- 异步调度（任务写入 `api_tasks` 表）
- 环境变量驱动（`CLOUD_CONFIDENCE_THRESHOLD`、`FORCE_LOCAL`、`DAILY_BUDGET`）

**测试结果**: 9 项单元测试全部通过（配置、预算、路由、Provider、降级、环境变量）

### Sprint 4: 后台服务层 ✅
- FastAPI 应用骨架（生命周期管理、CORS、全局异常处理）
- 中间件层（`LoggingMiddleware`、`RateLimitMiddleware`、`AuthMiddleware`）
- 推理 API（同步 `/api/inference/sync` + 异步 `/api/inference/async`）
- 任务管理 API（`/api/tasks` 列表/详情/取消）
- 统计 API（`/api/stats` 汇总/每日统计）
- WebSocket 实时推送（`/api/ws`，推理进度/任务完成/同步进度）
- PostgreSQL 云端数据库（asyncpg 连接池，7 张表：users、user_devices、sync_log、recognition_records_cloud、conversations_cloud、usage_stats_cloud）
- 数据同步引擎（增量同步、`last_write_wins` 冲突解决）
- OSS 图片上传（阿里云/腾讯云，模拟模式 + 预签名 URL）
- JWT 认证（access_token + refresh_token + FastAPI 依赖注入）
- 微信/Apple ID 第三方登录（抽象客户端架构）
- 手机号验证码登录（PBKDF2 密码哈希）
- Redis 任务队列（优雅降级到内存队列）
- Docker Compose 部署（FastAPI + PostgreSQL + Redis）

**测试结果**: 13 项单元测试全部通过（配置、JWT、密码、验证码、OSS、同步、队列、WebSocket）

### Sprint 5: 模型打包流水线 ✅
- 模型量化（`quantize.py`）：GPTQ / AWQ / INT8 / FP16 多后端统一接口
- ONNX 导出（`export_onnx.py`）：optimum + torch.onnx.export 双后端 fallback
- 性能测试（`benchmark.py`）：single / batch / stress 三种模式，P50/P95/P99 延迟统计
- 回归测试（`validate.py`）：文本/语义相似度、延迟回退检测、阈值判定
- 模型发布（`publish.py`）：local / S3 / OSS / COS / HF Hub 五目标支持
- 流水线编排（`pipeline.py`）：JSON 配置驱动、dry-run、自动 manifest

**测试结果**: 39 项单元测试全部通过（配置、结果类、工具方法、流水线、集成测试）

### Sprint 6: Android 客户端 ✅
- Android 项目骨架（Gradle Kotlin DSL + Jetpack Compose）
- CameraX 相机集成（预览、拍照、闪光灯、实时帧分析）
- ONNX Runtime Mobile 端侧推理引擎（模型预热、NCHW 预处理）
- Room Database + SQLCipher AES-256 加密数据库
- Foreground Service 后台常驻识别（通知栏保活、自动循环）
- Jetpack Compose UI（拍照页、历史页、设置页、对话页、登录页、同步页）
- Retrofit 网络层（对接 Sprint 4 FastAPI 后端）
- Material3 主题（亮/暗模式、自定义配色）

**测试结果**: 10 项单元测试通过（实体、网络数据类、工具方法）

### Sprint 7: iOS 适配 ✅
- iOS 项目骨架（Swift Package + SwiftUI + iOS 17+）
- AVFoundation 相机集成（前后切换、闪光灯、YUV 帧分析、UIViewRepresentable 预览）
- Core ML 端侧推理引擎（CVPixelBuffer 预处理、Neural Engine 自动选择）
- Core Data 持久化（程序化模型定义、3 实体、Data Protection 加密）
- Keychain 安全存储（Token/密钥/用户凭证、生物识别访问控制）
- BGTaskScheduler 后台任务（BGAppRefreshTask + BGProcessingTask）
- WidgetKit 小组件扩展（小/中/大三尺寸、快速拍照入口）
- SwiftUI UI（拍照页、历史页、设置页、对话页、登录页、同步页）
- URLSession 网络层（JWT 自动注入、JSON 编解码）
- Sign in with Apple 预留

**测试结果**: 13 项单元测试通过（Core Data、Keychain、API 模型、推理结果、同步状态）

## 目录结构

```
MiniCPM-V/
├── app/                        # 应用核心代码
│   ├── engine/                 # Sprint 1: 端侧推理引擎
│   │   ├── model_loader.py     # 模型加载（单例、预热、ModelScope）
│   │   ├── inference_engine.py # 推理引擎（LRU 缓存、线程安全）
│   │   ├── image_processor.py  # 图像处理（加载、验证、哈希）
│   │   ├── result_parser.py    # 结果解析（置信度、标签提取）
│   │   └── __init__.py
│   ├── data/                   # Sprint 2: 数据持久层
│   │   ├── database.py         # SQLite 连接管理 + CRUD 基类
│   │   ├── models.py           # 6 张表的 dataclass 定义
│   │   ├── dao_recognition.py  # 识别记录 DAO
│   │   ├── dao_conversation.py # 多轮对话 DAO
│   │   ├── dao_api_tasks.py    # API 任务队列 DAO
│   │   ├── dao_settings.py     # 用户设置 DAO
│   │   ├── dao_usage.py        # 使用统计 DAO
│   │   ├── migrations.py       # 数据库版本迁移
│   │   └── __init__.py
│   ├── api/                    # Sprint 3: API 调度引擎
│   │   ├── router.py           # 核心路由引擎（调度决策）
│   │   ├── budget.py           # 预算控制（日限额、自动降级）
│   │   ├── fallback.py         # 降级策略（端侧重试）
│   │   ├── config.py           # 调度引擎配置
│   │   ├── providers/          # 云端 Provider
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Provider 基类
│   │   │   ├── qwen.py         # 通义千问 VL 适配
│   │   │   └── doubao.py       # 豆包视觉适配
│   │   └── __init__.py
│   ├── service/                # Sprint 4: 后台服务层
│   │   ├── app.py              # FastAPI 应用骨架
│   │   ├── config.py           # 服务配置
│   │   ├── middleware.py       # 鉴权、限流、日志
│   │   ├── task_queue.py       # Redis 任务队列
│   │   ├── websocket.py        # WebSocket 实时推送
│   │   ├── test_service.py     # 13 项测试
│   │   ├── db/
│   │   │   ├── postgres.py     # PostgreSQL 连接池
│   │   │   ├── schema.sql      # 云端数据库 Schema
│   │   │   └── sync_engine.py  # 数据同步引擎
│   │   ├── auth/
│   │   │   ├── jwt.py          # JWT 认证
│   │   │   ├── oauth.py        # 第三方登录
│   │   │   └── password.py     # 密码/验证码登录
│   │   ├── oss/
│   │   │   └── client.py       # 对象存储客户端
│   │   └── routes/
│   │       ├── inference.py    # 推理 API
│   │       ├── tasks.py        # 任务管理 API
│   │       └── stats.py        # 统计 API
│   ├── ml/                     # Sprint 5: 模型打包流水线
│   │   ├── packaging/
│   │   │   ├── quantize.py     # 模型量化（GPTQ/AWQ/INT8）
│   │   │   ├── export_onnx.py  # ONNX 导出
│   │   │   ├── benchmark.py    # 性能测试
│   │   │   ├── validate.py     # 回归测试
│   │   │   ├── publish.py      # 模型发布
│   │   │   ├── pipeline.py     # 流水线编排
│   │   │   └── __init__.py
│   │   ├── test_packaging.py   # 39 项测试
│   │   └── __init__.py
│   ├── config.py               # 全局配置
│   ├── test_inference.py       # Sprint 1 测试脚本
│   ├── test_database.py        # Sprint 2 测试脚本
│   ├── test_api_scheduler.py   # Sprint 3 测试脚本
│   └── service/test_service.py # Sprint 4 测试脚本
├── docker-compose.yml          # Docker Compose 部署
├── autodl_training/            # AutoDL 训练脚本（Sprint 0）
│   ├── 01_setup_autodl_env.sh
│   ├── 02_download_datasets.py
│   ├── 03_train_lora.sh
│   ├── 04_train_full.sh
│   └── README.md
├── mobile/                     # Sprint 6: Android 客户端
│   └── android/
│       ├── app/build.gradle.kts
│       ├── app/src/main/
│       │   ├── AndroidManifest.xml
│       │   ├── java/com/minicpmv/app/
│       │   │   ├── MiniCPMVApplication.kt
│       │   │   ├── MainActivity.kt
│       │   │   ├── camera/CameraManager.kt
│       │   │   ├── data/AppDatabase.kt
│       │   │   ├── data/entity/
│       │   │   ├── data/dao/
│       │   │   ├── inference/OnnxInferenceEngine.kt
│       │   │   ├── service/RecognitionForegroundService.kt
│       │   │   ├── network/
│       │   │   ├── viewmodel/MainViewModel.kt
│       │   │   └── ui/
│       │   └── res/
│       ├── build.gradle.kts
│       └── settings.gradle.kts
├── docs/                       # 文档
│   └── 产业级_App_实施报告.md
├── TASKS.md                    # 完整任务清单
├── sync.ps1                    # 本地→云端同步脚本
└── README.md                   # 本文件
```

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 模型 | MiniCPM-V 4.6 | 1.3B 参数 |
| 推理框架 | Transformers | >= 5.7.0 |
| 模型调度 | accelerate | >= 0.30.1 |
| 模型下载 | ModelScope | 国内免登录 |
| 运行环境 | AutoDL GPU | CUDA + PyTorch 2.x |
| 同步工具 | sync.ps1 | scp / rsync |
| 后台服务 | FastAPI + Uvicorn | 0.139+ |
| 云端数据库 | PostgreSQL + asyncpg | 16 |
| 任务队列 | Redis | 7 |
| 图片存储 | 阿里云 OSS / 腾讯云 COS | SDK |
| 认证 | PyJWT + PBKDF2 | HS256 |
| 模型量化 | auto-gptq / auto-awq / bitsandbytes | INT4/INT8 |
| ONNX 导出 | optimum[onnxruntime] / torch.onnx | opset 14 |
| 模型发布 | boto3 / oss2 / huggingface_hub | S3/OSS/HF |
| **Android UI** | **Jetpack Compose** | **BOM 2024.02** |
| **Android 相机** | **CameraX** | **1.3.1** |
| **Android 推理** | **ONNX Runtime Mobile** | **1.16.3** |
| **Android 数据库** | **Room + SQLCipher** | **2.6.1 + 4.5.4** |
| **Android 网络** | **Retrofit + OkHttp** | **2.9.0** |
| **iOS UI** | **SwiftUI** | **iOS 17+** |
| **iOS 推理** | **Core ML** | **系统框架** |
| **iOS 数据库** | **Core Data + Data Protection** | **系统框架** |
| **iOS 安全** | **Keychain** | **系统框架** |
| **iOS 后台** | **BGTaskScheduler** | **系统框架** |

## 快速开始

### 云端运行（AutoDL）

```bash
# 1. 同步代码（本地 PowerShell）
cd D:\MiniCPM-V
.\sync.ps1

# 2. 云端运行测试
cd /root/autodl-tmp/MiniCPM-V/app
python test_inference.py
```

### 环境要求

```bash
pip install transformers>=5.7.0 accelerate>=0.30.1 modelscope torch
```

## Android 客户端快速开始

```bash
# 1. 打开 Android Studio，导入 mobile/android 目录
# 2. 同步 Gradle，等待依赖下载完成
# 3. 连接设备或启动模拟器（API 26+）
# 4. 点击 Run 按钮部署
```

## 下一步

**Sprint 8: 上架与监控** — 隐私合规、Crashlytics、性能打磨、灰度发布

详见 [TASKS.md](./TASKS.md) 完整任务清单。

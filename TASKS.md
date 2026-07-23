# MiniCPM-V 端侧视觉助手 - 完整任务清单

> 最后更新: 2026-07-24

## 项目目标

基于 MiniCPM-V 4.6 构建产业级移动端视觉助手 App，实现端侧实时拍照识别、多轮问答、后台常驻任务、云端 API 调度与本地数据库。

---

## 任务总览

| 阶段 | 任务 | 状态 | 说明 |
|------|------|------|------|
| Sprint 0 | 项目初始化与环境搭建 | ✅ 完成 | 仓库分析、AutoDL 环境、SSH 免密同步 |
| Sprint 1 | 端侧推理引擎 | ✅ 完成 | 6 个 Python 模块，4.6 模型加载+推理+缓存 |
| Sprint 2 | 数据持久层 | ✅ 完成 | SQLite + DAO + 6 张表 + 事务管理 |
| Sprint 3 | API 调度引擎 | ✅ 完成 | 端云协同、置信度路由、自动降级、云端 Provider 适配 |
| Sprint 4 | 后台服务层 | ✅ 完成 | FastAPI 服务、云端数据库、同步引擎、OSS、用户认证 |
| Sprint 5 | 模型打包流水线 | ✅ 完成 | ONNX 导出、量化(GPTQ/AWQ/INT8)、benchmark、回归测试、发布 |
| Sprint 6 | Android 客户端 | ✅ 完成 | CameraX、ONNX Runtime Mobile、Room + SQLCipher、Foreground Service |
| Sprint 7 | iOS 适配 | ✅ 完成 | Swift/SwiftUI、AVFoundation、Core ML、Core Data、Keychain、BGTask |
| Sprint 8 | 上架与监控 | ✅ 完成 | 隐私合规、Crashlytics、Sentry、Prometheus+Grafana、灰度发布、A/B 测试 |

---

## Sprint 0: 项目初始化与环境搭建 ✅

- [x] 克隆 MiniCPM-V 官方仓库，分析 9 个历史版本
- [x] 生成完整分析报告（11 章节 HTML）
- [x] 生成技术规划路线图（5 个研究方向、12 个场景）
- [x] 生成 App 架构设计（4 层、6 张表）
- [x] AutoDL 环境配置（Python 3.12、CUDA、PyTorch 2.x）
- [x] SSH 免密登录配置（ed25519 密钥）
- [x] sync.ps1 本地→云端代码同步脚本
- [x] ModelScope 模型下载方案（国内免登录）
- [x] 产业级 App 实施报告

## Sprint 1: 端侧推理引擎 ✅

- [x] `config.py` - 全局配置（模型、设备、缓存、推理参数）
- [x] `engine/model_loader.py` - 模型加载器（单例、预热、ModelScope 下载）
- [x] `engine/image_processor.py` - 图像处理（加载、验证、MD5 哈希）
- [x] `engine/inference_engine.py` - 推理引擎（LRU 缓存、线程安全、批量推理）
- [x] `engine/result_parser.py` - 结果解析（置信度、标签、JSON 提取）
- [x] `engine/__init__.py` - 模块导出
- [x] `test_inference.py` - 测试脚本（基础推理、缓存验证、benchmark）
- [x] MiniCPM-V 4.6 模型适配（AutoModelForImageTextToText + AutoProcessor）
- [x] processor_kwargs.images_kwargs 正确传参方式
- [x] 云端测试通过（加载 5.8s，推理 2.3s，显存 2.5GB）

## Sprint 2: 数据持久层 ✅

- [x] `data/database.py` - SQLite 连接管理（WAL 模式、线程隔离）、CRUD 基类
- [x] `data/models.py` - 6 张表的 dataclass / schema 定义
- [x] `data/dao_recognition.py` - 识别记录 DAO（hash 查询、同步标记、统计）
- [x] `data/dao_conversation.py` - 多轮对话 DAO（外键关联、token 统计）
- [x] `data/dao_image_index.py` - 图片向量索引 DAO（预留 BLOB 字段）
- [x] `data/dao_api_tasks.py` - API 任务队列 DAO（状态管理、重试、取消）
- [x] `data/dao_settings.py` - 用户设置 DAO（JSON 序列化、类型快捷方法）
- [x] `data/dao_usage.py` - 使用统计 DAO（日聚合、预算检查、累计统计）
- [x] `data/migrations.py` - 数据库版本迁移（schema_version 表、增量升级）
- [x] `data/__init__.py` - 统一模块导出
- [x] `test_database.py` - 7 项单元测试全部通过（含事务回滚验证）

### 数据库表设计

```
recognition_records: id, image_hash, image_path, question, answer, confidence,
                     model_version, device_id, task_type, synced, created_at, updated_at
conversations:       id, record_id, role, content, token_count, created_at
image_index:         id, image_hash, embedding_vector(BLOB), embedding_version,
                     indexed_at
api_tasks:           id, record_id, provider, status, retry_count, last_error,
                     scheduled_at, completed_at, created_at
user_settings:       key, value, updated_at
usage_stats:         date, local_count, api_count, tokens_used, cost, created_at
```

### 设计亮点

- **WAL 模式**：`PRAGMA journal_mode=WAL` 提升读写并发性能
- **线程隔离**：每个线程独立连接，通过 `threading.local()` 实现
- **SAVEPOINT 嵌套事务**：`transaction()` 上下文管理器支持嵌套回滚
- **自动 commit**：`execute()` 在非事务模式下自动提交，事务模式下静默
- **JSON 设置存储**：`settings_dao` 自动序列化/反序列化任意 Python 类型
- **日聚合统计**：`usage_dao` 使用 `ON CONFLICT(date) DO UPDATE` 实现高效累加

### 为云端扩展预留的字段（Sprint 4 使用）

当前 Sprint 2 的表结构已为 Sprint 4 的云端数据库和用户体系预留了关键字段：

| 字段 | 所在表 | 预留用途 | Sprint 4 使用方式 |
|------|--------|---------|------------------|
| `synced` | `recognition_records` | 云端同步标记 | 同步引擎查询未同步记录 |
| `device_id` | `recognition_records` | 多设备区分 | 云端 `user_devices` 表关联 |
| `image_hash` | `recognition_records` | 云端去重 | OSS 上传前检查重复 |
| `updated_at` | `recognition_records` | 冲突检测 | `last_write_wins` 策略的时间戳 |
| `record_id` | `api_tasks` | 端云任务关联 | 关联本地记录与云端任务 |
| `provider` | `api_tasks` | 云端 Provider 选择 | 路由到通义千问/豆包/OpenAI |
| `embedding_vector` | `image_index` | 语义向量 | 同步到 Milvus/Pinecone 向量数据库 |

## Sprint 3: API 调度引擎 ✅

- [x] `api/config.py` - 调度引擎配置（阈值、成本、Provider 列表）
- [x] `api/router.py` - API 路由引擎（按置信度、任务类型、成本选择端/云）
- [x] `api/providers/base.py` - 云端 Provider 基类（统一接口 + 返回格式）
- [x] `api/providers/qwen.py` - 通义千问 VL API 适配（HTTP API）
- [x] `api/providers/doubao.py` - 豆包视觉 API 适配（HTTP API）
- [x] `api/budget.py` - 预算控制（token 计数、日限额、自动降级）
- [x] `api/fallback.py` - 降级策略（云端失败→端侧重试，详细 prompt）
- [x] `api/__init__.py` + `providers/__init__.py` - 模块导出
- [x] 单元测试：9 项测试全部通过（配置、预算、路由、Provider、降级、环境变量）

### 架构设计

```
用户请求
    ↓
SchedulerRouter.schedule()
    ├── 1. 任务类型路由 → 强制端侧/强制云端/混合
    ├── 2. 预算检查 → 预算超限则降级端侧
    ├── 3. 端侧推理 → 置信度 >= 阈值则返回
    ├── 4. 云端 API → 按优先级尝试 Provider
    │   ├── QwenProvider (qwen-vl-plus)
    │   └── DoubaoProvider (doubao-vision-pro-32k)
    └── 5. 降级策略 → 全部失败则端侧重试
```

### 设计亮点

- **环境变量驱动**：置信度阈值、预算、强制模式可通过 `CLOUD_CONFIDENCE_THRESHOLD`、`FORCE_LOCAL`、`DAILY_BUDGET` 环境变量覆盖
- **Provider 插件化**：新增 Provider 只需继承 `BaseProvider` 实现 `_call_api()` 方法
- **预算联动**：`BudgetController` 与 Sprint 2 的 `settings_dao` 和 `usage_dao` 联动，支持持久化预算配置
- **TYPE_CHECKING 隔离**：`api` 层通过 `TYPE_CHECKING` 避免直接依赖 `engine` 层（防止 torch 不必要的导入）
- **异步调度**：`schedule_async()` 将任务写入 `api_tasks` 表，供后续 Sprint 的后台服务消费
- **双 Provider 适配**：Qwen 和 Doubao 均使用兼容 OpenAI 格式的 HTTP API，切换成本低

## Sprint 4: 后台服务层 ✅

- [x] `service/app.py` - FastAPI 应用骨架（生命周期管理、CORS、全局异常处理）
- [x] `service/config.py` - 服务配置（数据库、Redis、OSS、JWT、验证码、限流）
- [x] `service/middleware.py` - 鉴权、限流、日志中间件（滑动窗口限流、可选认证）
- [x] `service/routes/inference.py` - 推理 API 端点（同步 + 异步）
- [x] `service/routes/tasks.py` - 任务管理端点（列表、详情、取消）
- [x] `service/routes/stats.py` - 统计端点（汇总统计、每日统计）
- [x] `service/task_queue.py` - Redis 任务队列（优雅降级到内存队列）
- [x] `service/websocket.py` - 实时推送（连接管理、推理进度、任务完成、同步进度）
- [x] `service/db/postgres.py` - PostgreSQL 云端数据库连接池（asyncpg，单例）
- [x] `service/db/schema.sql` - 云端数据库 Schema（7 张表，含用户、设备、同步日志）
- [x] `service/db/sync_engine.py` - 数据同步引擎（增量同步、冲突解决 last_write_wins）
- [x] `service/oss/client.py` - 阿里云/腾讯云 OSS 图片上传（预签名 URL、去重、模拟模式）
- [x] `service/auth/jwt.py` - JWT 认证（access_token + refresh_token + 依赖注入）
- [x] `service/auth/oauth.py` - 微信/Apple ID 第三方登录（抽象客户端 + 具体实现）
- [x] `service/auth/password.py` - 手机号验证码登录（PBKDF2 密码哈希 + 短信验证码）
- [x] 单元测试：13 项测试全部通过（配置、JWT、密码、验证码、OSS、同步、队列、WebSocket）
- [x] Docker Compose 部署配置（FastAPI + PostgreSQL + Redis）

### 新增依赖

```bash
pip install fastapi uvicorn asyncpg redis httpx PyJWT python-multipart
```

### 架构设计

```
客户端请求
    ↓
FastAPI (create_app)
    ├── 中间件
    │   ├── LoggingMiddleware    # 请求日志（含慢请求告警）
    │   ├── RateLimitMiddleware  # IP 限流（滑动窗口，60 次/分钟）
    │   └── AuthMiddleware       # 可选认证（公开路径放行）
    ├── 路由
    │   ├── /api/inference/sync  # 同步推理
    │   ├── /api/inference/async # 异步推理（写入任务队列）
    │   ├── /api/tasks           # 任务管理
    │   ├── /api/stats           # 统计
    │   └── /api/ws              # WebSocket 实时推送
    ├── 云端服务
    │   ├── PostgreSQL (asyncpg) # 用户、设备、同步日志
    │   ├── Redis                # 任务队列
    │   └── OSS (阿里云/腾讯云)  # 图片存储
    └── 端侧引擎
        ├── SQLite (本地)        # 识别记录、对话、设置
        ├── 推理引擎             # MiniCPM-V 4.6
        └── 调度引擎             # 端云协同路由
```

### 设计亮点

- **环境变量驱动**：全部配置通过 `SERVICE_*` 环境变量覆盖，无需修改代码
- **可选认证**：公开路径自动放行，其他路径自动解析 Bearer Token
- **滑动窗口限流**：基于 IP 的请求限流，压力过大时返回 429
- **Redis 优雅降级**：Redis 不可用时自动切换到内存队列，不影响服务运行
- **OSS 模拟模式**：未配置 AccessKey 时使用本地文件系统模拟，方便开发测试
- **PBKDF2 密码哈希**：使用 hashlib 内置算法，无需第三方依赖，避免版本兼容问题
- **OAuth 抽象客户端**：新增第三方登录只需继承 `OAuthClient` 实现两个方法
- **同步冲突解决**：`last_write_wins` 策略，后续可扩展为向量时钟

## Sprint 5: 模型打包流水线 ✅

- [x] `ml/packaging/quantize.py` - 模型量化脚本（GPTQ / AWQ / INT8 / FP16）
  - 支持 4 种量化方案：GPTQ(INT4)、AWQ(INT4)、INT8(bitsandbytes)、FP16
  - 自动校准数据集加载（支持自定义数据集）
  - 压缩比计算和详细元数据输出
- [x] `ml/packaging/export_onnx.py` - ONNX 导出（PyTorch → ONNX）
  - 支持 optimum.exporters.onnx（推荐）和 torch.onnx.export（fallback）
  - 动态轴配置（支持变长 batch/sequence）
  - ONNX Runtime 图优化和 INT8 量化
- [x] `ml/packaging/benchmark.py` - 性能测试（延迟/内存/吞吐）
  - 3 种测试模式：single（单图）、batch（批量）、stress（压力/内存泄漏）
  - P50/P95/P99 延迟统计、TTFT/TPOT 测量
  - 内存泄漏检测（线性回归趋势分析）
- [x] `ml/packaging/validate.py` - 回归测试（输出一致性验证）
  - 文本相似度（Jaccard）和语义相似度（n-gram）
  - 延迟回退检测（量化后性能变化）
  - 阈值驱动的通过/失败判定
- [x] `ml/packaging/publish.py` - 模型发布（Artifact 打包上传）
  - 5 种发布目标：local、S3、OSS、COS、Hugging Face Hub
  - 自动模型卡片生成（README.md）
  - SHA256 校验和与打包（tar.gz / zip）
- [x] `ml/packaging/pipeline.py` - 流水线编排
  - 配置驱动（JSON），支持步骤跳过和 dry-run
  - 自动 manifest 生成（执行清单）
  - 错误处理和步骤中断机制
- [x] 单元测试：`ml/test_packaging.py` - 39 项测试全部通过

### 设计亮点

- **多后端量化**：GPTQ(auto-gptq/optimum)、AWQ(auto-awq)、INT8(bitsandbytes) 统一接口
- **ONNX 双后端**：optimum 失败自动 fallback 到 torch.onnx.export
- **Dry Run 模式**：流水线支持模拟执行，方便测试和调试
- **配置驱动**：所有步骤通过 JSON 配置，无需修改代码即可调整参数
- **内存泄漏检测**：压力测试使用线性回归分析内存趋势，自动判定泄漏
- **多目标发布**：一套代码支持本地、S3、OSS、COS、HF 五种发布目标

## Sprint 6: Android 客户端 ✅

- [x] `mobile/android/app/` - Android 项目骨架（Gradle Kotlin DSL + Jetpack Compose）
- [x] CameraX 集成（拍照、实时预览、闪光灯、缩放）
- [x] ONNX Runtime Mobile 集成（端侧推理、模型预热、NCHW 预处理）
- [x] Room Database 集成（3 张表、Flow 响应式查询、外键级联删除）
- [x] **SQLCipher 数据库加密**（AES-256 加密，SupportOpenHelperFactory）
- [x] Foreground Service（后台常驻、自动识别循环、通知栏状态）
- [x] 对话 UI（多轮问答、消息气泡、自动滚动）
- [x] 设置页（自动识别开关、云端授权、预算限额、置信度阈值、WiFi 同步）
- [x] 历史记录页（搜索、删除、同步状态标记、类型标签）
- [x] 登录/注册页（手机号验证码、微信登录预留）
- [x] 数据同步管理页（手动同步、同步状态机、冲突提示）
- [x] Retrofit 网络层（对接 Sprint 4 后端 API、Gson 序列化）
- [x] 单元测试：10 项测试（实体、网络数据类、工具方法）

### Android 技术栈

| 组件 | 技术 | 版本 |
|---|---|---|
| 语言 | Kotlin | 1.9.20 |
| UI | Jetpack Compose | BOM 2024.02.00 |
| 相机 | CameraX | 1.3.1 |
| 推理 | ONNX Runtime Mobile | 1.16.3 |
| 数据库 | Room + SQLCipher | 2.6.1 + 4.5.4 |
| 网络 | Retrofit + OkHttp | 2.9.0 |
| 图片加载 | Coil | 2.5.0 |
| 导航 | Navigation Compose | 2.7.7 |
| 状态管理 | ViewModel + Compose State | 2.7.0 |

### 核心文件列表

```
mobile/android/app/src/main/java/com/minicpmv/app/
├── MiniCPMVApplication.kt          # 应用入口（数据库/推理引擎延迟初始化）
├── MainActivity.kt                   # Compose Navigation + BottomBar
├── camera/
│   └── CameraManager.kt              # CameraX 封装（预览/拍照/帧分析）
├── data/
│   ├── AppDatabase.kt                # Room + SQLCipher 加密数据库
│   ├── entity/
│   │   ├── RecognitionRecord.kt      # 识别记录实体
│   │   ├── Conversation.kt           # 对话消息实体
│   │   └── UserSetting.kt            # 用户设置实体 + 键名常量
│   └── dao/
│       ├── RecognitionRecordDao.kt   # 识别记录 DAO（搜索/同步标记）
│       ├── ConversationDao.kt        # 对话 DAO（Flow 查询）
│       └── UserSettingDao.kt         # 设置 DAO（类型便捷方法）
├── inference/
│   └── OnnxInferenceEngine.kt        # ONNX Runtime Mobile 推理引擎
├── service/
│   └── RecognitionForegroundService.kt # 前台服务（后台识别循环）
├── network/
│   ├── ApiService.kt                 # Retrofit API 接口
│   └── RetrofitClient.kt             # 单例客户端
├── viewmodel/
│   └── MainViewModel.kt              # 相机/推理/历史/设置/同步状态管理
└── ui/
    ├── theme/
    │   ├── Color.kt                  # 配色方案
    │   ├── Type.kt                   # 字体排版
    │   └── Theme.kt                  # Material3 主题（亮/暗）
    ├── camera/
    │   └── CameraScreen.kt           # 拍照页面（预览/结果卡片）
    ├── chat/
    │   └── ChatScreen.kt             # 对话页面（消息气泡）
    ├── history/
    │   └── HistoryScreen.kt          # 历史记录（搜索/列表）
    ├── settings/
    │   └── SettingsScreen.kt         # 设置（开关/滑块/同步按钮）
    ├── login/
    │   └── LoginScreen.kt            # 登录/注册（手机号+验证码）
    └── sync/
        └── SyncScreen.kt             # 同步管理（状态机 UI）
```

### 设计亮点

- **延迟初始化**：`MiniCPMVApplication` 中数据库和推理引擎使用 `by lazy`，首次访问时才创建
- **SupervisorJob**：应用级和 Service 级协程作用域使用 SupervisorJob，子协程失败不影响其他协程
- **Flow 响应式**：DAO 返回 `Flow<List<T>>`，Compose 使用 `collectAsStateWithLifecycle` 自动订阅
- **SQLCipher 加密**：`SupportOpenHelperFactory` 传入密码字节数组，数据库文件 AES-256 加密
- **前台服务保活**：`RecognitionForegroundService` 以 `START_STICKY` 启动，被杀死后自动重启
- **BottomBar 导航**：`Scaffold + NavigationBar + NavHost` 实现三标签页切换，状态自动保存

## Sprint 7: iOS 适配 ✅

- [x] `mobile/ios/` - iOS 项目骨架（Swift Package + SwiftUI + Info.plist）
- [x] AVFoundation 相机集成（前后切换、闪光灯、YUV 帧分析、UIViewRepresentable 预览）
- [x] Core ML 模型加载与推理（CVPixelBuffer 预处理、Neural Engine 自动选择）
- [x] Core Data 持久化（程序化模型定义、3 实体、Fetch/Save）
- [x] **Data Protection 数据库加密**（NSFileProtectionCompleteUntilFirstUserAuthentication）
- [x] **Keychain 安全存储**（Token/密钥/用户凭证、生物识别访问控制）
- [x] BGTaskScheduler 后台任务（BGAppRefreshTask 识别 + BGProcessingTask 同步）
- [x] Widget 扩展（小/中/大三种尺寸、最近识别展示、快速拍照入口）
- [x] 登录/注册页（手机号验证码、Sign in with Apple 预留）
- [x] 数据同步管理页（iCloud 同步开关、手动同步、同步状态机）
- [x] URLSession 网络层（JWT 自动注入、JSON 编解码、错误处理）
- [x] 单元测试：13 项测试（Core Data、Keychain、API 模型、推理结果、同步状态）

### iOS 技术栈

| 组件 | 技术 | 版本 |
|---|---|---|
| 语言 | Swift | 5.9 |
| UI | SwiftUI | iOS 17+ |
| 相机 | AVFoundation | 系统框架 |
| 推理 | Core ML | 系统框架 |
| 数据库 | Core Data | 系统框架 |
| 加密 | Data Protection + Keychain | 系统框架 |
| 后台任务 | BGTaskScheduler | 系统框架 |
| 网络 | URLSession | 系统框架 |
| Widget | WidgetKit | 系统框架 |
| 认证 | Sign in with Apple | 系统框架 |

### 核心文件列表

```
mobile/ios/
├── Package.swift                          # SPM 配置
├── MiniCPMV/
│   ├── Info.plist                         # 权限 + 后台模式 + ATS
│   ├── Sources/
│   │   ├── MiniCPMVApp.swift              # 应用入口（AppState）
│   │   ├── ContentView.swift              # TabView 导航
│   │   ├── Theme/
│   │   │   └── AppTheme.swift             # 配色 + 字体
│   │   ├── Camera/
│   │   │   └── CameraManager.swift        # AVFoundation 封装
│   │   ├── Inference/
│   │   │   └── CoreMLInferenceEngine.swift # Core ML 推理
│   │   ├── Data/
│   │   │   ├── CoreDataStack.swift        # Core Data + Data Protection
│   │   │   └── CoreDataModel.swift        # 程序化模型定义
│   │   ├── Security/
│   │   │   └── KeychainManager.swift      # Keychain 安全存储
│   │   ├── Service/
│   │   │   ├── BackgroundTaskScheduler.swift # BGTaskScheduler
│   │   │   └── SyncManager.swift          # 数据同步引擎
│   │   ├── Network/
│   │   │   └── APIClient.swift            # URLSession API 客户端
│   │   └── Views/
│   │       ├── Camera/CameraView.swift    # 拍照页
│   │       ├── History/HistoryView.swift  # 历史页
│   │       ├── Settings/SettingsView.swift # 设置页
│   │       ├── Login/LoginView.swift      # 登录 + 对话页
│   │       └── Sync/SyncView.swift        # 同步页
│   └── Tests/
│       └── MiniCPMVTests.swift            # 13 项单元测试
└── Widget/
    └── Sources/
        └── MiniCPMVWidget.swift           # Widget 扩展
```

### 设计亮点

- **零第三方依赖**：iOS 端全部使用系统框架（AVFoundation/Core ML/Core Data/Keychain/BGTask/URLSession/WidgetKit），无需 SPM 第三方包
- **程序化 Core Data 模型**：通过代码定义 Entity（CoreDataModelBuilder），无需 .xcdatamodeld 可视化文件
- **Data Protection 加密**：Core Data 存储 配合 `NSFileProtectionCompleteUntilFirstUserAuthentication`，设备锁定后数据库自动加密
- **Keychain + 生物识别**：Token 存储支持 `SecAccessControlCreateWithFlags` + `.userPresence`，要求 Face ID/Touch ID 验证
- **BGTaskScheduler 双任务**：BGAppRefreshTask（轻量识别）+ BGProcessingTask（重度同步），合理利用 iOS 后台执行预算
- **Widget 三尺寸**：Small（快速启动）/ Medium（最近结果 + 拍照入口）/ Large（详细统计 + Link 跳转）
- **SwiftUI 声明式 UI**：Form + Section 分组设置页、ScrollViewReader 自动滚动对话、.regularMaterial 毛玻璃效果

## Sprint 8: 上架与监控 ✅

- [x] `compliance/privacy_policy.py` - 隐私政策与用户协议生成器（Markdown/HTML 双输出）
- [x] `compliance/data_compliance.py` - 数据安全合规管理器（GDPR 数据导出权、删除权、加密审计）
- [x] `compliance/store_checklist.py` - Google Play / App Store 上架合规清单（40+ 检查项）
- [x] `monitoring/crashlytics_config.py` - Firebase Crashlytics 崩溃监控配置（Android Gradle + iOS Swift + Kotlin 初始化）
- [x] `monitoring/sentry_config.py` - Sentry 性能监控配置（Python/Android/iOS 三端初始化 + 敏感数据过滤）
- [x] `monitoring/metrics.py` - Prometheus 后端指标采集器（30+ 指标定义，Prometheus 格式导出）
- [x] `monitoring/grafana_dashboard.py` - Grafana 仪表板构建器（12 面板 JSON 配置 + 6 条告警规则）
- [x] `performance/cold_start.py` - 冷启动优化器（5 阶段分阶段初始化、启动时间分析）
- [x] `performance/memory_manager.py` - 内存管理器（LRU 缓存淘汰、4 级内存警告响应、图片优化配置）
- [x] `performance/battery_optimizer.py` - 电池优化器（4 级电源模式自适应、WorkManager/BGTask 配置）
- [x] `release/gradual_rollout.py` - 灰度发布管理器（5 阶段分阶段发布、哈希分桶、自动回滚）
- [x] `release/ab_test.py` - A/B 测试框架（实验管理、确定性分桶、Z 检验显著性分析）
- [x] `release/migration_plan.py` - 数据库迁移方案（SQLite→PostgreSQL 双写过渡 6 阶段、可回滚）
- [x] 单元测试：84 项测试全部通过（合规 16 项、监控 22 项、性能 18 项、发布 28 项）

### Sprint 8 技术栈

| 组件 | 技术 | 用途 |
|---|---|---|
| 崩溃监控 | Firebase Crashlytics | Android/iOS 崩溃收集、ANR 检测 |
| 性能监控 | Sentry | 三端性能追踪、慢事务检测 |
| 后端指标 | Prometheus + Grafana | 30+ 指标采集、12 面板仪表板 |
| 冷启动优化 | 分阶段延迟初始化 | 目标 < 2 秒 |
| 内存管理 | LRU + 4 级警告响应 | 缓存淘汰、图片内存优化 |
| 电池优化 | 4 级电源模式自适应 | 推理频率/精度/分辨率动态调整 |
| 灰度发布 | 5 阶段哈希分桶 | 1%→5%→20%→50%→100% |
| A/B 测试 | Z 检验显著性分析 | 确定性分桶、置信度计算 |
| 数据迁移 | 双写过渡 6 阶段 | SQLite→PostgreSQL 零数据丢失 |

### 核心文件列表

```
app/
├── compliance/                      # 合规模块
│   ├── __init__.py
│   ├── privacy_policy.py            # 隐私政策生成器
│   ├── data_compliance.py           # GDPR 数据合规
│   └── store_checklist.py           # 商店上架清单
├── monitoring/                      # 监控模块
│   ├── __init__.py
│   ├── crashlytics_config.py        # Crashlytics 配置
│   ├── sentry_config.py             # Sentry 配置
│   ├── metrics.py                   # Prometheus 指标
│   └── grafana_dashboard.py         # Grafana 仪表板
├── performance/                     # 性能优化
│   ├── __init__.py
│   ├── cold_start.py                # 冷启动优化
│   ├── memory_manager.py            # 内存管理
│   └── battery_optimizer.py         # 电池优化
├── release/                         # 发布管理
│   ├── __init__.py
│   ├── gradual_rollout.py           # 灰度发布
│   ├── ab_test.py                   # A/B 测试
│   └── migration_plan.py            # 数据库迁移
└── test_sprint8.py                  # 84 项单元测试
```

### 设计亮点

- **隐私合规双输出**：`PrivacyPolicyGenerator` 同时生成 Markdown 和 HTML 格式隐私政策，覆盖 10 个章节
- **GDPR 三权保障**：`DataComplianceManager` 实现数据导出权（JSON/CSV）、删除权（验证哈希）、加密审计（8 项检查）
- **商店清单 40+ 项**：`StoreChecklistValidator` 覆盖 Google Play 和 App Store 合规要求，支持分类报告和 Markdown 输出
- **Crashlytics 三端配置**：一键生成 Android Gradle、iOS Swift、Kotlin 初始化代码，GDPR 合规（默认关闭、用户同意后开启）
- **Sentry 敏感数据过滤**：`SentryEventProcessor` 递归清理 Authorization/Cookie/Password 等敏感字段
- **Prometheus 30+ 指标**：覆盖 HTTP 请求、推理、端云协同、数据库、Redis、WebSocket、OSS、认证 8 大类
- **Grafana 12 面板**：KPI 卡片、延迟分布、端云对比、系统健康、同步统计、告警规则一体化
- **冷启动 5 阶段**：PRE_CREATE→APP_CREATE→POST_CREATE→FIRST_FRAME→IDLE，异步任务不阻塞启动
- **内存 4 级响应**：NORMAL→WARNING(清图片)→CRITICAL(清一半)→EMERGENCY(全清空)
- **电池 4 级模式**：PERFORMANCE(fp16/5s)→BALANCED(int8/15s)→LOW_POWER(int8/60s)→ULTRA_LOW(int4/300s)
- **灰度哈希分桶**：SHA256(user_id) % 10000 实现确定性分桶，用户每次分到相同变体
- **A/B Z 检验**：双比例 Z 检验判断显著性，自动推荐全量发布或继续实验
- **迁移 6 阶段**：PREPARATION→DUAL_WRITE→VERIFICATION→READ_SWITCH→SQLITE_READONLY→CLEANUP，每阶段可回滚

---

## 当前状态

- **已完成**: Sprint 0 + Sprint 1 + Sprint 2 + Sprint 3 + Sprint 4 + Sprint 5 + Sprint 6 + Sprint 7 + Sprint 8
- **项目状态**: 全部 Sprint 完成 ✅
- **模型**: MiniCPM-V 4.6（1.3B 参数，FP16，2.5GB 显存）
- **数据库**: SQLite（WAL 模式，6 张表，SAVEPOINT 嵌套事务）+ PostgreSQL（7 张表，asyncpg 连接池）
- **调度引擎**: 端云协同路由（置信度阈值、预算控制、Provider 插件化）
- **后台服务**: FastAPI + Docker Compose（含 PostgreSQL + Redis）
- **测试环境**: AutoDL GPU，transformers 5.7+，ModelScope 下载

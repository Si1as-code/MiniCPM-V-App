# MiniCPM-V 端侧视觉助手 - 完整任务清单

> 最后更新: 2026-07-23

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
| Sprint 6 | Android 客户端 | ⬜ 待开始 | 拍照 UI、Foreground Service、Room DB |
| Sprint 7 | iOS 适配 | ⬜ 待开始 | Widget、BGTask、Keychain |
| Sprint 8 | 上架与监控 | ⬜ 待开始 | 合规清单、Crashlytics、性能打磨 |

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

## Sprint 6: Android 客户端 ⬜

- [ ] `mobile/android/app/` - Android 项目骨架
- [ ] Camera X 集成（拍照、相册选取）
- [ ] ONNX Runtime Mobile 集成（端侧推理）
- [ ] Room Database 集成（本地数据持久）
- [ ] **SQLCipher 数据库加密**（敏感字段 AES-256 加密）
- [ ] **Android Keystore 密钥管理**（加密密钥安全存储）
- [ ] Foreground Service（后台常驻、自动识别）
- [ ] 对话 UI（多轮问答、流式输出）
- [ ] 设置页（自动识别开关、云端授权、预算限额）
- [ ] 历史记录页（搜索、筛选、导出）
- [ ] 登录/注册页（手机号验证码、微信登录）
- [ ] 数据同步管理页（手动同步、同步状态、冲突提示）

## Sprint 7: iOS 适配 ⬜

- [ ] `mobile/ios/app/` - iOS 项目骨架
- [ ] AVFoundation 相机集成
- [ ] Core ML 模型转换与加载
- [ ] Core Data 持久化
- [ ] **Data Protection 数据库加密**（NSFileProtectionComplete）
- [ ] **Keychain 安全存储**（Token、密钥、用户凭证）
- [ ] BGTaskScheduler 后台任务
- [ ] Widget 扩展（快速拍照识别）
- [ ] 登录/注册页（手机号验证码、Sign in with Apple）
- [ ] 数据同步管理页（iCloud 同步开关、手动同步）

## Sprint 8: 上架与监控 ⬜

- [ ] 隐私政策与用户协议
- [ ] Google Play / App Store 合规清单
- [ ] **数据安全合规**（GDPR/个人信息保护法 - 数据加密、删除权、导出权）
- [ ] Firebase Crashlytics 崩溃监控
- [ ] Sentry 性能监控
- [ ] Prometheus + Grafana 后端指标
- [ ] 性能打磨（冷启动、内存优化、电池策略）
- [ ] 灰度发布与 A/B 测试方案
- [ ] 数据库迁移方案（SQLite → PostgreSQL 双写过渡期）

---

## 当前状态

- **已完成**: Sprint 0 + Sprint 1 + Sprint 2 + Sprint 3 + Sprint 4
- **下一步**: Sprint 5（模型打包流水线）
- **模型**: MiniCPM-V 4.6（1.3B 参数，FP16，2.5GB 显存）
- **数据库**: SQLite（WAL 模式，6 张表，SAVEPOINT 嵌套事务）+ PostgreSQL（7 张表，asyncpg 连接池）
- **调度引擎**: 端云协同路由（置信度阈值、预算控制、Provider 插件化）
- **后台服务**: FastAPI + Docker Compose（含 PostgreSQL + Redis）
- **测试环境**: AutoDL GPU，transformers 5.7+，ModelScope 下载

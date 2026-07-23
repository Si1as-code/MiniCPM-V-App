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
| Sprint 2 | 数据持久层 | ⬜ 待开始 | SQLite + DAO + 6 张表 |
| Sprint 3 | API 调度引擎 | ⬜ 待开始 | 端云协同、置信度路由、自动降级 |
| Sprint 4 | 后台服务层 | ⬜ 待开始 | FastAPI 服务、任务队列、WebSocket |
| Sprint 5 | 模型打包流水线 | ⬜ 待开始 | ONNX 量化、benchmark、差分更新 |
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

## Sprint 2: 数据持久层 ⬜

- [ ] `data/database.py` - SQLite 连接管理、迁移、CRUD 基类
- [ ] `data/models.py` - 6 张表的 dataclass / schema 定义
- [ ] `data/dao_recognition.py` - 识别记录 DAO
- [ ] `data/dao_conversation.py` - 多轮对话 DAO
- [ ] `data/dao_image_index.py` - 图片向量索引 DAO（sqlite-vec）
- [ ] `data/dao_api_tasks.py` - API 任务队列 DAO
- [ ] `data/dao_settings.py` - 用户设置 DAO
- [ ] `data/dao_usage.py` - 使用统计 DAO
- [ ] `data/migrations.py` - 数据库版本迁移
- [ ] 单元测试：DAO 层 CRUD 验证

### 数据库表设计

```
recognition_records: id, image_hash, image_path, question, answer, confidence,
                     model_version, device_id, task_type, synced, created_at
conversations:       id, record_id, role, content, token_count, created_at
image_index:         id, image_hash, embedding_vector(BLOB), embedding_version,
                     indexed_at
api_tasks:           id, record_id, provider, status, retry_count, last_error,
                     scheduled_at, completed_at
user_settings:       key, value, updated_at
usage_stats:         date, local_count, api_count, tokens_used, cost
```

## Sprint 3: API 调度引擎 ⬜

- [ ] `api/router.py` - API 路由引擎（按置信度、任务类型、成本选择端/云）
- [ ] `api/providers/base.py` - 云端 Provider 基类
- [ ] `api/providers/qwen.py` - 通义千问 VL API 适配
- [ ] `api/providers/doubao.py` - 豆包视觉 API 适配
- [ ] `api/budget.py` - 预算控制（token 计数、日限额、自动降级）
- [ ] `api/fallback.py` - 降级策略（云端失败→端侧重试）
- [ ] 单元测试：路由决策、预算控制

## Sprint 4: 后台服务层 ⬜

- [ ] `service/app.py` - FastAPI 应用骨架
- [ ] `service/routes/inference.py` - 推理 API 端点
- [ ] `service/routes/tasks.py` - 任务管理端点
- [ ] `service/routes/stats.py` - 统计端点
- [ ] `service/task_queue.py` - Redis 任务队列
- [ ] `service/websocket.py` - 实时推送
- [ ] `service/middleware.py` - 鉴权、限流、日志
- [ ] Docker Compose 部署配置

## Sprint 5: 模型打包流水线 ⬜

- [ ] `ml/packaging/quantize.py` - GPTQ/AWQ 量化脚本
- [ ] `ml/packaging/export_onnx.py` - PyTorch → ONNX 转换
- [ ] `ml/packaging/benchmark.py` - 延迟/内存/吞吐 benchmark
- [ ] `ml/packaging/publish.py` - Artifact 发布（S3/GCS）
- [ ] `ml/packaging/validate.py` - 回归测试
- [ ] CI/CD pipeline 集成

## Sprint 6: Android 客户端 ⬜

- [ ] `mobile/android/app/` - Android 项目骨架
- [ ] Camera X 集成（拍照、相册选取）
- [ ] ONNX Runtime Mobile 集成（端侧推理）
- [ ] Room Database 集成（本地数据持久）
- [ ] Foreground Service（后台常驻、自动识别）
- [ ] 对话 UI（多轮问答、流式输出）
- [ ] 设置页（自动识别开关、云端授权、预算限额）
- [ ] 历史记录页（搜索、筛选、导出）

## Sprint 7: iOS 适配 ⬜

- [ ] `mobile/ios/app/` - iOS 项目骨架
- [ ] AVFoundation 相机集成
- [ ] Core ML 模型转换与加载
- [ ] Core Data 持久化
- [ ] BGTaskScheduler 后台任务
- [ ] Widget 扩展（快速拍照识别）
- [ ] Keychain 安全存储

## Sprint 8: 上架与监控 ⬜

- [ ] 隐私政策与用户协议
- [ ] Google Play / App Store 合规清单
- [ ] Firebase Crashlytics 崩溃监控
- [ ] Sentry 性能监控
- [ ] Prometheus + Grafana 后端指标
- [ ] 性能打磨（冷启动、内存优化、电池策略）
- [ ] 灰度发布与 A/B 测试方案

---

## 当前状态

- **已完成**: Sprint 0 + Sprint 1
- **下一步**: Sprint 2（数据持久层）
- **模型**: MiniCPM-V 4.6（1.3B 参数，FP16，2.5GB 显存）
- **测试环境**: AutoDL GPU，transformers 5.7+，ModelScope 下载

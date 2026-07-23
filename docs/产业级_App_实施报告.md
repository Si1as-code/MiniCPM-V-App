# MiniCPM-V 产业级移动端 App 实施报告

版本：2026-07-22

## 一、目标概述
实现面向移动端的产业级视觉助手，核心能力包括：
- 端侧实时拍照识别与多轮问答；
- 可选拍照后自动识别（用户开关）；
- 后台常驻任务（Android 前台服务）实现长期挂机并调度识别任务；
- 云端 API 调度与自动升级（置信度低或需联网时）；
- 完整的本地 + 可选云端数据库方案；
- 模型打包与移动端部署流水线；
- 上架合规、隐私与成本控制策略。

## 二、关键结论（高优先级修改点）
1. 时间线建议从原 12 周扩展到 14-16 周，预留模型量化、平台适配与上架测试时间。
2. 必须建立模型交付流水线（量化→转换→benchmark→发布），并记录模型签名与版本以支持回滚。
3. 平台差异：Android 可以实现长期后台；iOS 受限，应设计受限的替代 UX（Widget、用户触发、BGTask）。
4. 隐私默认策略：默认本地优先，云端增强前需用户明确授权；API Keys 使用系统安全存储（Keystore/Keychain）。
5. 向量索引在本地可用 sqlite-vec，但企业版应支持同步至 pgvector/Milvus。必须规范 embedding 格式与压缩策略。
6. 实施成本控制与限额：实现本地预算控制、token 计数与自动降级机制。
7. 生产级监控与日志：集成崩溃与性能监控（Crashlytics/Sentry）、云端指标采集（Prometheus/Grafana）。

## 三、架构摘要
- 四层：L1 用户交互（拍照/相册/语音）、L2 核心服务（端侧推理 + 结果解析）、L3 后台常驻（Foreground Service、任务队列）、L4 数据持久（SQLite 本地 + 可选云端 DB）。
- 推理：优先使用 ONNX Runtime Mobile（或平台原生 CoreML/NNAPI），模型按设备能力下发（INT4/INT8/FP16）。
- 后端：FastAPI（或 NestJS）+ PostgreSQL + pgvector + Redis（任务队列）作为可选企业版后端。

## 四、数据库设计要点
- 主要表：`recognition_records`, `conversations`, `image_index`, `api_tasks`, `user_settings`, `usage_stats`。
- `image_index.embedding_vector` 存 BLOB（float32）或使用本地 sqlite-vec 扩展；embedding 需归一化并存版本号。
- `recognition_records` 建议增加 `device_id`, `model_version`, `synced` 字段；`api_tasks` 增加 `retry_count`、`last_error`、`scheduled_at`。
- 索引：为 `image_hash`, `indexed_at` 建索引以保证查找性能。
- 数据治理：本地默认保留 90 天，可配置并支持用户导出/删除。

## 五、模型打包与交付流水线
1. 量化方案选择：GPTQ/AWQ（或厂商工具）→ 评估 INT4/INT8 trade-off。
2. 转换：PyTorch -> ONNX -> （TFLite/CoreML 如需）.
3. Benchmark：建立自动化脚本测延迟、内存、吞吐、功耗（短期热量模拟）。
4. Artifact 发布：上传到内部 Artifact 存储（S3/GCS），支持差分更新与按设备分发。
5. 验证：自动化回归测试（功能性输出对比、latency 基线）。

## 六、实现路线图（建议）
- Sprint 0（1 周）：可行性评估、工具链与 CI 初设。
- Sprint 1（2 周）：MVP-1：Android 原型，拍照→端侧推理→展示→写入本地 DB。
- Sprint 2（2 周）：MVP-2：Room DB、多轮对话保存、历史 UI。
- Sprint 3（2 周）：模型包装流水线（量化/ONNX/benchmark）。
- Sprint 4（2 周）：后台任务与保活（Foreground Service、截图/相册监听、优先级队列）。
- Sprint 5（2 周）：后端基础（FastAPI skeleton、api_tasks、本地队列交互）。
- Sprint 6（2 周）：相册索引与语义搜索（embedding 抽取、sqlite-vec 集成）。
- Sprint 7（2 周）：iOS 限制适配、隐私合规、Keychain/Keystore 集成。
- Sprint 8（1-3 周）：上架准备、性能打磨、监控埋点。

## 七、风险与缓解
- 模型体积/下载限制：使用 On-Demand Delivery、差分更新、用户确认下载。
- iOS 后台限制：将实时功能降级为用户触发/Widget/云端回调。
- 电池与发热：调度限频、冷却策略、用户设置阈值。
- 成本超支：本地预算计数器与自动降级、任务合并与采样率控制。

## 八、工程建议（仓库结构与 CI）
- 新增目录：`mobile/android/`, `mobile/ios/`, `backend/`, `ml/packaging/`, `infra/`。
- CI 增：模型转换 job、移动端构建 job、自动 benchmark job、后端集成测试。
- 文档：`docs/ModelPackaging.md`, `docs/PrivacyPolicy.md`, `docs/OnDeviceGuidelines.md`。

## 九、交付物（示例清单）
- Android MVP APK（拍照识别 + DB）；
- model-packages（ONNX INT4/INT8）与转换脚本；
- 后端 skeleton（Docker Compose）；
- 上架合规清单与隐私声明草案。

## 十、下一步
- 选项 A：把路线拆为任务清单（可导出为 Jira/Trello 卡片）；
- 选项 B：生成 Android PoC 代码骨架（Foreground Service + Room + ONNX 推理）；
- 选项 C：实现模型打包流水线脚本并在仓库中加入示例；
- 选项 D：搭建后端 FastAPI + Redis 最小 Task Router 并提供 Docker Compose。

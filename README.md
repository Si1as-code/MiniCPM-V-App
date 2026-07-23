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
│   ├── config.py               # 全局配置
│   ├── test_inference.py       # Sprint 1 测试脚本
│   ├── test_database.py        # Sprint 2 测试脚本
│   └── README.md
├── autodl_training/            # AutoDL 训练脚本（Sprint 0）
│   ├── 01_setup_autodl_env.sh
│   ├── 02_download_datasets.py
│   ├── 03_train_lora.sh
│   ├── 04_train_full.sh
│   └── README.md
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

## 下一步

**Sprint 3: API 调度引擎** — 端云协同、置信度路由、自动降级

详见 [TASKS.md](./TASKS.md) 完整任务清单。

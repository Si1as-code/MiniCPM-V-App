# Part 1: 端侧推理引擎

## 是什么

这是整个 MiniCPM-V App 的**核心推理引擎**——一个独立的 Python 模块，封装了模型加载、图片预处理、推理执行、结果解析的完整链路。后续所有模块（数据库、API 调度、后台服务）都依赖它。

## 技术栈

| 组件 | 技术 | 作用 |
|------|------|------|
| 语言 | Python 3.10+ | 主开发语言 |
| 深度学习 | PyTorch 2.x | 模型推理 |
| 模型框架 | Hugging Face Transformers | 模型加载与 Tokenizer |
| 图像处理 | Pillow (PIL) | 图片加载、格式转换 |
| 网络 | requests | 从 URL 下载图片 |
| 设计模式 | 单例模式 + 线程安全 | 全局唯一模型实例，推理串行 |

## 文件结构

```
app/
├── config.py              # 全局配置（模型名、设备、推理参数）
├── engine/
│   ├── __init__.py        # 模块导出
│   ├── model_loader.py    # 模型加载、卸载、预热、状态管理
│   ├── image_processor.py # 图片加载、验证、哈希缓存
│   ├── inference_engine.py # 核心推理编排（缓存 + 串行执行）
│   └── result_parser.py   # 结果解析、置信度估算、标签提取
├── test_inference.py      # 测试脚本
└── README.md              # 本文件
```

## 你需要做什么操作

### 1. 安装依赖

```bash
pip install torch transformers pillow requests
```

### 2. 在本地测试（CPU 模式，验证代码逻辑）

```bash
cd d:\MiniCPM-V\app
set DEVICE=cpu
set MODEL_NAME=openbmb/MiniCPM-V-2_6
python test_inference.py
```

> 注意：CPU 模式很慢且可能内存不足，仅用于验证代码能跑通。建议在 AutoDL GPU 上测试。

### 3. 在 AutoDL GPU 上测试（推荐）

```bash
# 1) 将 app/ 目录上传到 AutoDL
scp -P PORT -r d:\MiniCPM-V\app root@HOST:/root/autodl-tmp/

# 2) SSH 登录 AutoDL
ssh -p PORT root@HOST

# 3) 运行测试
cd /root/autodl-tmp/app
python test_inference.py --image /path/to/your/test.jpg
```

### 4. 指定自己的图片测试

```bash
python test_inference.py --image my_photo.jpg --question "这张图片里有什么？"
```

### 5. 性能基准测试

```bash
python test_inference.py --benchmark
```

## 你要验证什么

| 验证项 | 预期结果 | 不通过怎么办 |
|--------|----------|-------------|
| 模型加载 | 打印"模型加载完成"，显示 GPU 显存占用 | 检查 CUDA 版本、transformers 版本 |
| 基础推理 | 返回有意义的文字描述（非乱码） | 检查图片格式、模型是否完整下载 |
| 缓存生效 | 第二次推理速度远快于第一次（加速比 > 10x） | 检查 `enable_cache` 配置 |
| 性能基准 | 单次推理 < 5 秒（GPU） | 降低 `max_slice_nums`、使用 `16x` 降采样 |
| 测试图片 | 正确识别红蓝绿黄四个色块 | 如果识别错误，说明模型可能不擅长纯色块 |

## 核心 API 速览

```python
from config import config
from engine.model_loader import model_loader
from engine.inference_engine import inference_engine

# 1. 修改配置（可选）
config.model_name = "openbmb/MiniCPM-V-2_6"
config.downsample_mode = "16x"  # 快速模式

# 2. 加载模型
model_loader.load()

# 3. 推理
result = inference_engine.inference(
    image_source="path/to/image.jpg",
    question="描述这张图片"
)

# 4. 使用结果
print(result.formatted_text)       # 格式化的回答
print(result.confidence)           # 置信度
print(result.labels)               # 识别的标签
print(result.inference_time)       # 推理耗时

# 5. 查看状态
print(model_loader.model_info)     # 模型状态
print(inference_engine.get_stats()) # 引擎统计
```

## 从 Part 1 到 Part 2 的衔接

Part 1 跑通后，`InferenceResult` 对象就是 Part 2（数据库层）的输入。Part 2 会把这些结果存入 SQLite，实现识别历史、相册搜索等功能。

---

**下一步：确认 Part 1 跑通后，告诉我，我继续生成 Part 2（数据库层）。**
# MiniCPM-V AutoDL 远程训练完整指南

## 重要说明

**我无法直接通过 SSH 连接到您的 AutoDL 实例**。作为 AI 助手，我没有您的登录凭证（密码/密钥），也没有网络权限访问外部服务器。

**但我为您准备了一整套方案**：从 AutoDL 租用、环境配置、VS Code 远程开发到训练启动，您按照本指南操作，约 15 分钟即可搭建好"本地编辑 + 云端训练"的流畅工作流。

---

## 目录

1. [方案概述](#1-方案概述)
2. [AutoDL 租用与开机](#2-autodl-租用与开机)
3. [VS Code Remote-SSH 配置（核心）](#3-vscode-remote-ssh-配置核心)
4. [云端环境初始化](#4-云端环境初始化)
5. [数据集下载与准备](#5-数据集下载与准备)
6. [启动训练](#6-启动训练)
7. [本地修改云端同步的原理](#7-本地修改云端同步的原理)
8. [常见问题](#8-常见问题)

---

## 1. 方案概述

### 最终实现效果

```
您的本地电脑（无显卡）                    AutoDL 云端服务器（GPU）
┌──────────────────────┐                 ┌──────────────────────────────┐
│ 本地 VS Code 编辑器   │  ←── SSH ──→  │  VS Code Server（自动安装）   │
│ • 编辑代码            │    实时同步    │ • 运行 Python                │
│ • 查看训练日志        │    文件修改    │ • 执行训练脚本                │
│ • 调试代码            │                │ • GPU 训练                    │
└──────────────────────┘                 └──────────────────────────────┘
```

### 所需工具

| 工具 | 用途 | 下载地址 |
|------|------|----------|
| VS Code | 本地代码编辑器 | https://code.visualstudio.com/ |
| Remote-SSH 插件 | SSH 远程开发 | VS Code 扩展商店搜索安装 |
| AutoDL 账号 | 租用 GPU 服务器 | https://www.autodl.com/ |
| Git | 代码版本管理 | https://git-scm.com/ |

---

## 2. AutoDL 租用与开机

### 2.1 注册与充值

1. 访问 https://www.autodl.com/ 注册账号
2. 充值（训练 MiniCPM-V 建议至少充值 50 元）

### 2.2 选择合适的服务器

**推荐配置**（LoRA 微调）：

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| GPU | RTX 3090 (24GB) x1 | RTX 4090 (24GB) x2 或 A100 (40GB) |
| CPU | 8核 | 16核 |
| 内存 | 32GB | 64GB |
| 硬盘 | 100GB | 200GB+ |

**注意**：
- MiniCPM-V 2.6 LoRA 微调单卡 24GB 可以跑，但 batch size 只能设 1
- 全参数微调需要 A100 80GB 或同等显存
- 选择"基础镜像"中的 PyTorch 版本（如 PyTorch 2.1 + CUDA 12.1）

### 2.3 开机并获取 SSH 信息

1. 在 AutoDL 控制台选择服务器 → 点击"开机"
2. 开机后点击"SSH 登录"，复制 SSH 命令，例如：
   ```
   ssh -p 12345 root@connect.westb.seetacloud.com
   ```
3. 同时会显示登录密码，请保存好

---

## 3. VS Code Remote-SSH 配置（核心）

这一步是实现"本地修改、云端同步、远程训练"的关键。

### 3.1 安装 Remote-SSH 插件

1. 打开本地 VS Code
2. 点击左侧扩展图标（或按 `Ctrl+Shift+X`）
3. 搜索 `Remote - SSH`，点击安装

### 3.2 配置 SSH 连接

**方法一：通过命令面板配置（推荐）**

1. 按 `F1` 或 `Ctrl+Shift+P` 打开命令面板
2. 输入并选择：`Remote-SSH: Connect to Host...`
3. 选择 `+ Add New SSH Host`
4. 输入 AutoDL 提供的 SSH 命令：
   ```
   ssh -p 12345 root@connect.westb.seetacloud.com
   ```
   （将 `12345` 和域名替换为您的实际信息）
5. 选择保存到 `C:\Users\您的用户名\.ssh\config`

**方法二：手动编辑 config 文件**

1. 打开文件：`C:\Users\您的用户名\.ssh\config`
2. 添加以下内容：
   ```
   Host autodl-minicpm
       HostName connect.westb.seetacloud.com
       Port 12345
       User root
   ```

### 3.3 连接远程服务器

1. 再次按 `F1`，选择 `Remote-SSH: Connect to Host...`
2. 选择刚才配置的 `autodl-minicpm`
3. 选择平台类型：`Linux`
4. 输入密码（AutoDL 提供的登录密码）
5. 等待 VS Code Server 在云端自动安装（首次连接约 1-2 分钟）

### 3.4 打开项目文件夹

连接成功后：
1. 点击 `Open Folder`
2. 输入项目路径：`/root/autodl-tmp/minicpm-v-training/MiniCPM-V`
3. 再次输入密码
4. 现在您看到的文件列表就是 **云端服务器上的文件**

### 3.5 关键理解：这就是"同步"

**VS Code Remote-SSH 的工作方式**：

- 您在本地 VS Code 中打开的是 **远程文件系统**
- 您的每一次保存（`Ctrl+S`）都直接保存到云端服务器
- 终端（`Ctrl+``）运行的是云端服务器的 Shell
- Python 解释器使用的是云端服务器的 Python

**因此不存在"同步"问题**——您就在直接编辑云端文件，修改即时生效。

---

## 4. 云端环境初始化

在 VS Code 的远程终端中（按 `Ctrl+``），依次执行：

### 4.1 上传本脚本到云端

您可以将本目录下的脚本通过 VS Code 直接复制到云端，或者：

```bash
# 在云端创建目录
mkdir -p /root/autodl-tmp/minicpm-v-training
cd /root/autodl-tmp/minicpm-v-training

# 从 GitHub 克隆项目
git clone https://github.com/OpenBMB/MiniCPM-V.git
```

### 4.2 运行环境初始化脚本

```bash
cd /root/autodl-tmp/minicpm-v-training/MiniCPM-V
bash 01_setup_autodl_env.sh
```

此脚本会自动：
- 检查 GPU 和 CUDA 环境
- 安装项目依赖（requirements.txt）
- 安装训练依赖（peft、deepspeed、accelerate）
- 配置 Hugging Face 缓存目录

---

## 5. 数据集下载与准备

### 5.1 创建演示数据（快速验证）

```bash
cd /root/autodl-tmp/minicpm-v-training/MiniCPM-V
python 02_download_datasets.py --dataset demo
```

这会创建一个 `demo_data.json`，不需要真实图像，仅用于验证训练流程是否能跑通。

### 5.2 下载真实数据集（正式训练）

**推荐数据集**：LLaVA-Instruct-150K

```bash
# 安装 huggingface-cli
pip install huggingface-hub -q

# 下载数据集（国内建议加镜像）
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download liuhaotian/LLaVA-Instruct-150K \
    --local-dir /root/autodl-tmp/minicpm-v-training/data/llava \
    --repo-type dataset

# 同时下载 COCO 图像数据
# （LLaVA 使用 COCO train2017 作为图像源）
```

### 5.3 转换数据格式

```bash
python 02_download_datasets.py --dataset llava \
    --output_dir /root/autodl-tmp/minicpm-v-training/data \
    --image_dir /root/autodl-tmp/minicpm-v-training/data/llava/images
```

---

## 6. 启动训练

### 6.1 修改训练脚本参数

用 VS Code 打开 `03_train_lora.sh`，修改以下参数：

```bash
# 根据您的数据路径修改
DATA="/root/autodl-tmp/minicpm-v-training/data/demo_data.json"

# 根据 GPU 显存调整
MAX_SLICE_NUMS=9        # 显存不足可降到 5 或 1
MODEL_MAX_LENGTH=2048   # 可降低到 1024 节省显存

# 训练步数
MAX_STEPS=1000          # 正式训练建议 10000+
```

### 6.2 启动 LoRA 微调

在 VS Code 远程终端中：

```bash
cd /root/autodl-tmp/minicpm-v-training/MiniCPM-V
bash 03_train_lora.sh
```

### 6.3 监控训练

**方式一：查看日志文件**

```bash
# 实时查看训练日志
tail -f /root/autodl-tmp/minicpm-v-training/output/lora_*/training.log
```

**方式二：TensorBoard**

```bash
# 在云端启动 TensorBoard
tensorboard --logdir=/root/autodl-tmp/minicpm-v-training/output/ --port=6006

# 在本地浏览器访问（通过 SSH 端口转发）
# VS Code 会自动提示端口转发，点击即可
```

### 6.4 训练完成后使用模型

```python
from peft import PeftModel
from transformers import AutoModel

# 加载基础模型
model = AutoModel.from_pretrained(
    'openbmb/MiniCPM-V-2_6',
    trust_remote_code=True
)

# 加载 LoRA 权重
model = PeftModel.from_pretrained(
    model,
    '/root/autodl-tmp/minicpm-v-training/output/lora_xxxx'
)

# 合并权重（可选，合并后无需 PEFT 依赖）
model = model.merge_and_unload()
```

---

## 7. 本地修改云端同步的原理

很多用户会困惑"本地修改怎么同步到云端"。使用 VS Code Remote-SSH 后，这个问题根本不存在：

### 传统方案 vs Remote-SSH 方案

| 方式 | 本地编辑 | 同步机制 | 训练执行 |
|------|----------|----------|----------|
| 传统 FTP/SCP | 本地文件 | 手动上传 | SSH 登录后运行 |
| rsync 自动同步 | 本地文件 | 定时/触发同步 | SSH 登录后运行 |
| **VS Code Remote-SSH** | **云端文件（本地编辑）** | **无需同步** | **一键运行** |
| PyCharm 远程解释器 | 本地文件 | 自动上传 | 远程运行 |

### Remote-SSH 的本质

Remote-SSH 不是"把本地文件同步到远程"，而是：

1. 本地 VS Code 作为**编辑器前端**
2. 云端运行 **VS Code Server** 作为后端
3. 文件读写直接发生在**云端文件系统**
4. Python 解释器、终端、调试器都在**云端运行**

**您看到的文件列表就是云端的文件，您的保存就是保存到云端，您的运行就是在云端 GPU 上运行。**

### 如果您确实需要"本地有一份代码，同时云端也训练"

可以用 Git 管理：

```bash
# 本地修改后提交
git add .
git commit -m "更新训练配置"
git push

# 云端拉取更新
git pull
bash 03_train_lora.sh
```

或者使用 PyCharm Professional 的"Deployment"功能自动同步。

---

## 8. 常见问题

### Q1: 连接超时或失败？

- 确认 AutoDL 实例已开机
- 检查 SSH 端口和地址是否正确
- 尝试在本地终端手动 SSH 测试：`ssh -p 12345 root@connect.westb.seetacloud.com`

### Q2: 显存不足（OOM）？

```bash
# 降低图像切片数
MAX_SLICE_NUMS=1

# 降低最大序列长度
MODEL_MAX_LENGTH=1024

# 使用 DeepSpeed ZeRO3
DEEPSPEED_CONFIG="ds_config_zero3.json"

# 开启梯度检查点（需修改 finetune.py 添加）
```

### Q3: 模型下载慢？

```bash
# 使用 Hugging Face 国内镜像
export HF_ENDPOINT=https://hf-mirror.com

# 或者使用 modelscope
pip install modelscope -q
python -c "from modelscope import snapshot_download; snapshot_download('OpenBMB/MiniCPM-V-2_6')"
```

### Q4: 训练中断后如何恢复？

```bash
# 在训练脚本中添加 --resume_from_checkpoint
--resume_from_checkpoint "/root/autodl-tmp/minicpm-v-training/output/lora_xxxx/checkpoint-500"
```

### Q5: 如何下载训练好的模型到本地？

```bash
# 在本地 PowerShell/CMD 中运行
scp -P 12345 -r root@connect.westb.seetacloud.com:/root/autodl-tmp/minicpm-v-training/output/lora_xxxx D:\MiniCPM-V\my_model
```

---

## 附录：文件清单

| 文件 | 用途 |
|------|------|
| `01_setup_autodl_env.sh` | 云端环境初始化 |
| `02_download_datasets.py` | 数据集下载与格式转换 |
| `03_train_lora.sh` | LoRA 微调启动脚本 |
| `04_train_full.sh` | 全参数微调启动脚本 |
| `README.md` | 本指南 |

---

**祝训练顺利！如有问题，可以参考 AutoDL 官方文档或 MiniCPM-V GitHub Issues。**

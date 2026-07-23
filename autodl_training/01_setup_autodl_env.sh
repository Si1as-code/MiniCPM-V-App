#!/bin/bash
# ============================================================================
# MiniCPM-V AutoDL 云端环境初始化脚本
# 在 AutoDL 实例开机后，通过 SSH 登录并运行此脚本
# 运行方式: bash 01_setup_autodl_env.sh
# ============================================================================

set -e  # 遇到错误立即退出

echo "========================================"
echo "MiniCPM-V AutoDL 环境初始化"
echo "========================================"

# ----------------------------------------------------------------------------
# 1. 检查 CUDA 和 GPU
# ----------------------------------------------------------------------------
echo "[1/6] 检查 GPU 和 CUDA 环境..."
nvidia-smi
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"

# ----------------------------------------------------------------------------
# 2. 创建工作目录
# ----------------------------------------------------------------------------
echo "[2/6] 创建工作目录..."
WORK_DIR="/root/autodl-tmp/minicpm-v-training"
mkdir -p $WORK_DIR
cd $WORK_DIR
mkdir -p data models output logs

# ----------------------------------------------------------------------------
# 3. 克隆项目代码（如果尚未克隆）
# ----------------------------------------------------------------------------
echo "[3/6] 拉取 MiniCPM-V 代码..."
if [ ! -d "MiniCPM-V" ]; then
    git clone https://github.com/OpenBMB/MiniCPM-V.git
else
    echo "MiniCPM-V 目录已存在，跳过克隆"
fi

cd MiniCPM-V

# ----------------------------------------------------------------------------
# 4. 安装 Python 依赖
# ----------------------------------------------------------------------------
echo "[4/6] 安装 Python 依赖..."

# 升级基础包
pip install --upgrade pip setuptools wheel -q

# 安装 PyTorch（AutoDL 通常已预装，但确保版本正确）
# 如需要特定 CUDA 版本，请修改下面的命令
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装项目依赖
pip install -r requirements.txt -q

# 安装训练相关依赖
pip install peft deepspeed accelerate transformers datasets -q

# 安装可选但推荐的依赖
pip install wandb tensorboard flash-attn --no-build-isolation -q 2>/dev/null || echo "flash-attn 安装失败，跳过（非必须）"

echo "依赖安装完成"

# ----------------------------------------------------------------------------
# 5. 创建 Hugging Face 缓存目录（用于存储下载的模型）
# ----------------------------------------------------------------------------
echo "[5/6] 配置 Hugging Face 缓存..."
export HF_HOME="/root/autodl-tmp/hf-cache"
mkdir -p $HF_HOME

# 配置 HF 镜像（国内加速）
# 如需使用镜像，取消下面注释
# export HF_ENDPOINT=https://hf-mirror.com

echo "HF_HOME=$HF_HOME"

# ----------------------------------------------------------------------------
# 6. 预下载模型（可选，加速后续训练）
# ----------------------------------------------------------------------------
echo "[6/6] 预下载模型（此步骤可选，会占用磁盘空间）..."
echo "如需预下载模型，请手动运行:"
echo "  python -c \"from transformers import AutoModel; AutoModel.from_pretrained('openbmb/MiniCPM-V-2_6', trust_remote_code=True)\""

echo ""
echo "========================================"
echo "环境初始化完成！"
echo "工作目录: $WORK_DIR"
echo ""
echo "下一步:"
echo "  1. 运行数据集下载脚本: python download_datasets.py"
echo "  2. 配置训练参数并启动训练: bash train_lora.sh"
echo "========================================"

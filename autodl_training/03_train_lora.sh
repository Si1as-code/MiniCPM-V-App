#!/bin/bash
# ============================================================================
# MiniCPM-V LoRA 微调启动脚本（适配 AutoDL）
# 根据您的 GPU 配置和训练需求修改下方参数
# 运行方式: bash 03_train_lora.sh
# ============================================================================

set -e

# ----------------------------------------------------------------------------
# 用户配置区（请根据实际情况修改）
# ----------------------------------------------------------------------------

# 模型选择
# 可选: openbmb/MiniCPM-V-2_6, openbmb/MiniCPM-Llama3-V-2_5, openbmb/MiniCPM-V-2, openbmb/MiniCPM-o-2_6
MODEL="openbmb/MiniCPM-V-2_6"

# 语言模型类型
# llama for MiniCPM-V-4, minicpm for MiniCPM-V-2, llama3 for MiniCPM-Llama3-V-2_5, qwen for MiniCPM-o-2_6/MiniCPM-V-2_6
LLM_TYPE="qwen"

# 数据路径
DATA="/root/autodl-tmp/minicpm-v-training/data/demo_data.json"
EVAL_DATA="/root/autodl-tmp/minicpm-v-training/data/demo_data.json"

# 输出目录
OUTPUT_DIR="/root/autodl-tmp/minicpm-v-training/output/lora_$(date +%Y%m%d_%H%M%S)"

# 训练参数
MAX_STEPS=1000          # 训练步数（演示用 1000，正式训练建议 10000+）
EVAL_STEPS=100          # 每多少步评估一次
SAVE_STEPS=100          # 每多少步保存一次检查点
LOGGING_STEPS=10        # 每多少步记录日志
MAX_SLICE_NUMS=9        # 图像切片数（降低可减少显存占用）
MODEL_MAX_LENGTH=2048   # 最大序列长度（多图 SFT 建议 4096）

# GPU 配置（AutoDL 通常单节点多卡）
GPUS_PER_NODE=$(nvidia-smi -L | wc -l)  # 自动检测 GPU 数量
NNODES=1
NODE_RANK=0
MASTER_ADDR=localhost
MASTER_PORT=6001

# LoRA 参数
LORA_RANK=64            # LoRA 秩，越大表达能力越强但参数越多
LORA_ALPHA=128          # LoRA alpha，通常设为 2*rank
LORA_DROPOUT=0.05

# DeepSpeed 配置
DEEPSPEED_CONFIG="ds_config_zero2.json"  # 可选: ds_config_zero2.json, ds_config_zero3.json

# ----------------------------------------------------------------------------
# 分布式训练参数
# ----------------------------------------------------------------------------
DISTRIBUTED_ARGS="
    --nproc_per_node $GPUS_PER_NODE
    --nnodes $NNODES
    --node_rank $NODE_RANK
    --master_addr $MASTER_ADDR
    --master_port $MASTER_PORT
"

# ----------------------------------------------------------------------------
# 打印配置信息
# ----------------------------------------------------------------------------
echo "========================================"
echo "MiniCPM-V LoRA 微调配置"
echo "========================================"
echo "模型: $MODEL"
echo "LLM类型: $LLM_TYPE"
echo "数据: $DATA"
echo "输出: $OUTPUT_DIR"
echo "GPU数量: $GPUS_PER_NODE"
echo "训练步数: $MAX_STEPS"
echo "LoRA Rank: $LORA_RANK"
echo "DeepSpeed: $DEEPSPEED_CONFIG"
echo "========================================"

mkdir -p $OUTPUT_DIR

# ----------------------------------------------------------------------------
# 启动训练
# ----------------------------------------------------------------------------
torchrun $DISTRIBUTED_ARGS finetune/finetune.py \
    --model_name_or_path $MODEL \
    --llm_type $LLM_TYPE \
    --data_path $DATA \
    --eval_data_path $EVAL_DATA \
    --remove_unused_columns false \
    --label_names "labels" \
    --prediction_loss_only false \
    --bf16 false \
    --bf16_full_eval false \
    --fp16 true \
    --fp16_full_eval true \
    --do_train \
    --do_eval \
    --tune_vision true \
    --tune_llm false \
    --use_lora true \
    --lora_rank $LORA_RANK \
    --lora_alpha $LORA_ALPHA \
    --lora_dropout $LORA_DROPOUT \
    --lora_target_modules "llm\..*layers\.\d+\.self_attn\.(q_proj|k_proj|v_proj|o_proj)" \
    --model_max_length $MODEL_MAX_LENGTH \
    --max_slice_nums $MAX_SLICE_NUMS \
    --max_steps $MAX_STEPS \
    --eval_steps $EVAL_STEPS \
    --save_steps $SAVE_STEPS \
    --logging_steps $LOGGING_STEPS \
    --output_dir $OUTPUT_DIR \
    --logging_dir $OUTPUT_DIR/logs \
    --per_device_train_batch_size 1 \
    --per_device_eval_batch_size 1 \
    --gradient_accumulation_steps 1 \
    --evaluation_strategy "steps" \
    --save_strategy "steps" \
    --save_total_limit 3 \
    --learning_rate 1e-4 \
    --weight_decay 0.1 \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --deepspeed finetune/$DEEPSPEED_CONFIG \
    --report_to tensorboard \
    2>&1 | tee $OUTPUT_DIR/training.log

echo ""
echo "========================================"
echo "训练完成！"
echo "输出目录: $OUTPUT_DIR"
echo "日志文件: $OUTPUT_DIR/training.log"
echo "========================================"

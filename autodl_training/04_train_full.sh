#!/bin/bash
# ============================================================================
# MiniCPM-V 全参数微调启动脚本（适配 AutoDL，需 A100 80G 或同等显存）
# 全参数微调比 LoRA 需要更多显存，请确保 GPU 显存充足
# 运行方式: bash 04_train_full.sh
# ============================================================================

set -e

# ----------------------------------------------------------------------------
# 用户配置区
# ----------------------------------------------------------------------------
MODEL="openbmb/MiniCPM-V-2_6"
LLM_TYPE="qwen"
DATA="/root/autodl-tmp/minicpm-v-training/data/demo_data.json"
EVAL_DATA="/root/autodl-tmp/minicpm-v-training/data/demo_data.json"
OUTPUT_DIR="/root/autodl-tmp/minicpm-v-training/output/full_$(date +%Y%m%d_%H%M%S)"

MAX_STEPS=1000
EVAL_STEPS=100
SAVE_STEPS=100
MODEL_MAX_LENGTH=2048
MAX_SLICE_NUMS=9

GPUS_PER_NODE=$(nvidia-smi -L | wc -l)
NNODES=1
NODE_RANK=0
MASTER_ADDR=localhost
MASTER_PORT=6001

# 全参数微调必须使用 ZeRO3 并开启 offload
DEEPSPEED_CONFIG="ds_config_zero3.json"

# ----------------------------------------------------------------------------
DISTRIBUTED_ARGS="
    --nproc_per_node $GPUS_PER_NODE
    --nnodes $NNODES
    --node_rank $NODE_RANK
    --master_addr $MASTER_ADDR
    --master_port $MASTER_PORT
"

echo "========================================"
echo "MiniCPM-V 全参数微调配置"
echo "========================================"
echo "模型: $MODEL"
echo "GPU数量: $GPUS_PER_NODE"
echo "DeepSpeed: $DEEPSPEED_CONFIG"
echo "========================================"

mkdir -p $OUTPUT_DIR

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
    --tune_llm true \
    --use_lora false \
    --model_max_length $MODEL_MAX_LENGTH \
    --max_slice_nums $MAX_SLICE_NUMS \
    --max_steps $MAX_STEPS \
    --eval_steps $EVAL_STEPS \
    --save_steps $SAVE_STEPS \
    --output_dir $OUTPUT_DIR \
    --per_device_train_batch_size 1 \
    --per_device_eval_batch_size 1 \
    --gradient_accumulation_steps 1 \
    --evaluation_strategy "steps" \
    --save_strategy "steps" \
    --learning_rate 2e-5 \
    --weight_decay 0.1 \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --deepspeed finetune/$DEEPSPEED_CONFIG \
    --report_to tensorboard \
    2>&1 | tee $OUTPUT_DIR/training.log

echo ""
echo "========================================"
echo "全参数微调完成！"
echo "输出目录: $OUTPUT_DIR"
echo "========================================"

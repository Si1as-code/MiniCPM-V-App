#!/usr/bin/env python3
# ============================================================================
# MiniCPM-V 训练数据集下载与准备脚本
# 支持下载公开数据集并转换为 MiniCPM-V 微调所需的 JSON 格式
# 运行方式: python 02_download_datasets.py
# ============================================================================

import os
import json
import argparse
from pathlib import Path
from urllib.request import urlretrieve
from tqdm import tqdm

# ----------------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------------
DATA_ROOT = "/root/autodl-tmp/minicpm-v-training/data"
Path(DATA_ROOT).mkdir(parents=True, exist_ok=True)

# 公开可用的多模态指令微调数据集
DATASET_URLS = {
    "llava_instruct_150k": {
        "url": "https://huggingface.co/datasets/liuhaotian/LLaVA-Instruct-150K/resolve/main/chat.json",
        "description": "LLaVA 指令微调数据（150K 样本）",
        "format": "llava"
    },
    # 如需更多数据集，可在此添加
}

# ----------------------------------------------------------------------------
# 数据格式转换函数
# ----------------------------------------------------------------------------

def convert_llava_to_minicpmv(llava_data, image_root):
    """
    将 LLaVA 格式数据转换为 MiniCPM-V 微调格式
    LLaVA 格式: {id, image, conversations: [{from, value}]}
    MiniCPM-V 格式: {id, image, conversations: [{role, content}]}
    """
    converted = []
    for item in tqdm(llava_data, desc="转换数据格式"):
        try:
            # 构建图像路径
            image_path = os.path.join(image_root, item.get("image", ""))
            
            # 转换对话格式
            conversations = []
            for conv in item.get("conversations", []):
                role = "user" if conv.get("from") == "human" else "assistant"
                content = conv.get("value", "")
                # 将 <image> 标记统一格式
                content = content.replace("<image>", "<image>")
                conversations.append({
                    "role": role,
                    "content": content
                })
            
            converted.append({
                "id": item.get("id", "unknown"),
                "image": image_path,
                "conversations": conversations
            })
        except Exception as e:
            print(f"跳过样本 {item.get('id', 'unknown')}: {e}")
            continue
    
    return converted


def create_demo_dataset(output_path, num_samples=100):
    """
    创建演示数据集（用于快速验证训练流程）
    不需要真实图像，仅用于测试代码是否跑通
    """
    demo_data = []
    for i in range(num_samples):
        demo_data.append({
            "id": f"demo_{i}",
            "image": "path/to/your/image.jpg",  # 请替换为实际路径
            "conversations": [
                {
                    "role": "user",
                    "content": "<image>\n请描述这张图片。"
                },
                {
                    "role": "assistant",
                    "content": "这是一张示例图片，用于验证训练流程。"
                }
            ]
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(demo_data, f, ensure_ascii=False, indent=2)
    
    print(f"演示数据集已创建: {output_path} ({num_samples} 条)")
    return demo_data


def download_file(url, output_path):
    """带进度条的文件下载"""
    print(f"下载: {url}")
    
    class TqdmUpTo(tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)
    
    with TqdmUpTo(unit='B', unit_scale=True, miniters=1) as t:
        urlretrieve(url, filename=output_path, reporthook=t.update_to)
    
    print(f"已保存到: {output_path}")


# ----------------------------------------------------------------------------
# 主函数
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MiniCPM-V 数据集下载与准备")
    parser.add_argument("--dataset", type=str, default="demo", 
                        choices=["demo", "llava", "all"],
                        help="选择要准备的数据集: demo(演示数据), llava(LLaVA指令数据), all(全部)")
    parser.add_argument("--output_dir", type=str, default=DATA_ROOT,
                        help="数据输出目录")
    parser.add_argument("--image_dir", type=str, default=None,
                        help="图像文件目录（用于构建完整路径）")
    
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    # ------------------------------------------------------------------------
    # 1. 创建演示数据集（用于快速验证）
    # ------------------------------------------------------------------------
    if args.dataset in ["demo", "all"]:
        print("=" * 60)
        print("创建演示数据集...")
        print("=" * 60)
        demo_path = os.path.join(args.output_dir, "demo_data.json")
        create_demo_dataset(demo_path, num_samples=100)
        print("")
    
    # ------------------------------------------------------------------------
    # 2. 下载 LLaVA 数据
    # ------------------------------------------------------------------------
    if args.dataset in ["llava", "all"]:
        print("=" * 60)
        print("准备 LLaVA Instruct 数据集...")
        print("=" * 60)
        
        # 注意：LLaVA 数据需要从官方渠道下载
        # 这里提供转换脚本，假设用户已下载原始数据
        llava_raw_path = os.path.join(args.output_dir, "llava_raw.json")
        llava_converted_path = os.path.join(args.output_dir, "llava_minicpmv_format.json")
        
        if os.path.exists(llava_raw_path):
            print(f"找到原始数据: {llava_raw_path}")
            with open(llava_raw_path, 'r', encoding='utf-8') as f:
                llava_data = json.load(f)
            
            image_root = args.image_dir or os.path.join(args.output_dir, "images")
            converted = convert_llava_to_minicpmv(llava_data, image_root)
            
            with open(llava_converted_path, 'w', encoding='utf-8') as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)
            
            print(f"转换完成: {llava_converted_path} ({len(converted)} 条)")
        else:
            print(f"未找到原始数据: {llava_raw_path}")
            print("请手动下载 LLaVA 数据到该路径，然后重新运行此脚本")
            print("")
            print("下载方式:")
            print("  1. 从 Hugging Face 下载: https://huggingface.co/datasets/liuhaotian/LLaVA-Instruct-150K")
            print("  2. 使用 huggingface-cli:")
            print("     huggingface-cli download liuhaotian/LLaVA-Instruct-150K --local-dir ./data/llava")
            print("")
    
    # ------------------------------------------------------------------------
    # 3. 显示数据格式说明
    # ------------------------------------------------------------------------
    print("=" * 60)
    print("数据格式说明")
    print("=" * 60)
    print("""
MiniCPM-V 微调需要的 JSON 格式示例:

[
  {
    "id": "0",
    "image": "/path/to/image.jpg",
    "conversations": [
      {"role": "user", "content": "<image>\\n描述这张图片"},
      {"role": "assistant", "content": "这是一张..."}
    ]
  }
]

关键说明:
- <image> 是图像占位符，必须包含在对话中
- 多图场景使用 <image_00>, <image_01> 等占位符
- image 字段可以是字符串（单图）或字典（多图）
- 建议单条数据 token 数不超过 2048（多图 SFT 可设 4096）
""")
    
    print("=" * 60)
    print("数据集准备完成！")
    print(f"输出目录: {args.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()

"""
============================================================================
端侧推理引擎 - 测试脚本
============================================================================
用法:
    python test_inference.py                    # 使用默认测试图片
    python test_inference.py --image cat.jpg    # 指定图片路径
    python test_inference.py --image cat.jpg --question "图中有几只猫？"
    python test_inference.py --benchmark         # 性能基准测试
============================================================================
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# 确保能找到 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from engine.model_loader import model_loader
from engine.inference_engine import inference_engine
from engine.image_processor import load_image, compute_image_hash

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test")


def generate_test_image():
    """生成一张测试用的纯色图片（四色块）"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (512, 512), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 四个象限各一个色块
    draw.rectangle((0, 0, 256, 256), fill=(0, 0, 255))       # 蓝
    draw.rectangle((256, 0, 512, 256), fill=(255, 0, 0))     # 红
    draw.rectangle((0, 256, 256, 512), fill=(0, 255, 0))     # 绿
    draw.rectangle((256, 256, 512, 512), fill=(255, 255, 0))  # 黄

    test_path = Path(__file__).parent / "test_image.png"
    img.save(test_path)
    return test_path


def test_basic_inference(image_path: str, question: str):
    """基础推理测试"""
    print("=" * 60)
    print("测试 1: 基础推理")
    print("=" * 60)

    result = inference_engine.inference(
        image_source=image_path,
        question=question,
    )

    print(f"\n📷 图片: {image_path}")
    print(f"❓ 问题: {question}")
    print(f"⏱️ 耗时: {result.inference_time:.2f}s")
    print(f"🎯 置信度: {result.confidence:.2f}")
    print(f"🏷️ 标签: {', '.join(result.labels) if result.labels else '无'}")
    print(f"\n📝 回答:\n{result.formatted_text}\n")

    return result


def test_cache(image_path: str):
    """缓存测试"""
    print("=" * 60)
    print("测试 2: 结果缓存")
    print("=" * 60)

    # 第一次推理
    t1 = time.time()
    r1 = inference_engine.inference(image_source=image_path, force_reload=True)
    t1 = time.time() - t1

    # 第二次推理（应该命中缓存）
    t2 = time.time()
    r2 = inference_engine.inference(image_source=image_path)
    t2 = time.time() - t2

    print(f"\n首次推理: {t1:.2f}s")
    print(f"缓存命中: {t2:.2f}s")
    print(f"加速比: {t1/t2:.1f}x")
    print(f"结果一致: {r1.formatted_text == r2.formatted_text}")


def test_benchmark(image_path: str, rounds: int = 3):
    """性能基准测试"""
    print("=" * 60)
    print(f"测试 3: 性能基准测试 (连续 {rounds} 次)")
    print("=" * 60)

    times = []
    for i in range(rounds):
        # 使用 force_reload 跳过缓存，测试真实推理速度
        t_start = time.time()
        result = inference_engine.inference(
            image_source=image_path,
            force_reload=True,
        )
        elapsed = time.time() - t_start
        times.append(elapsed)
        print(f"  第 {i+1} 次: {elapsed:.2f}s")

    avg = sum(times) / len(times)
    print(f"\n📊 平均耗时: {avg:.2f}s")
    print(f"📊 最快: {min(times):.2f}s")
    print(f"📊 最慢: {max(times):.2f}s")

    # 模型信息
    info = model_loader.model_info
    print(f"\n模型信息: {info}")


def main():
    parser = argparse.ArgumentParser(
        description="MiniCPM-V 端侧推理引擎测试"
    )
    parser.add_argument(
        "--image", "-i", type=str, default=None,
        help="测试图片路径（不指定则生成测试图片）"
    )
    parser.add_argument(
        "--question", "-q", type=str,
        default="请描述这张图片的内容，包括颜色和形状。",
        help="推理问题"
    )
    parser.add_argument(
        "--benchmark", "-b", action="store_true",
        help="运行性能基准测试"
    )
    parser.add_argument(
        "--model", "-m", type=str, default=None,
        help="指定模型名称（覆盖配置）"
    )
    args = parser.parse_args()

    # 覆盖模型配置
    if args.model:
        config.model_name = args.model

    # 准备测试图片
    if args.image:
        image_path = args.image
    else:
        print("未指定图片，生成测试图片...")
        image_path = str(generate_test_image())

    print(f"\n{'='*60}")
    print(f"MiniCPM-V 端侧推理引擎 - 测试")
    print(f"{'='*60}")
    print(f"模型: {config.model_name}")
    print(f"设备: {config.device}")
    print(f"图片: {image_path}")
    print(f"问题: {args.question}")
    print(f"{'='*60}\n")

    # 1. 加载模型
    print("正在加载模型...")
    model_loader.load()
    print(f"模型加载完成! 信息: {model_loader.model_info}\n")

    # 2. 基础推理
    test_basic_inference(image_path, args.question)

    # 3. 缓存测试
    test_cache(image_path)

    # 4. 基准测试（可选）
    if args.benchmark:
        test_benchmark(image_path)

    # 5. 统计
    print("=" * 60)
    print("引擎统计:")
    print("=" * 60)
    for k, v in inference_engine.get_stats().items():
        print(f"  {k}: {v}")

    print("\n✅ 所有测试完成!")


if __name__ == "__main__":
    main()
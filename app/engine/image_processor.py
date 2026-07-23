"""
============================================================================
图像处理器 - 图片加载、预处理、哈希缓存
============================================================================
技术栈: PIL (Pillow), hashlib, NumPy
关键点:
  - 支持本地文件路径、URL、PIL.Image 对象三种输入
  - 计算图片 MD5 哈希用于结果缓存（避免重复推理）
  - 图片预处理（resize、格式转换）适配模型输入
============================================================================
"""

import hashlib
import io
import logging
from pathlib import Path
from typing import Union, Optional, Tuple

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# 支持的图片格式
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def load_image(
    source: Union[str, Path, Image.Image, bytes]
) -> Image.Image:
    """
    统一图片加载接口

    支持三种输入:
      1) 本地文件路径 ("/path/to/image.jpg")
      2) HTTP URL ("https://example.com/image.jpg")
      3) PIL.Image 对象 (直接返回)

    Args:
        source: 图片来源

    Returns:
        PIL.Image: RGB 格式的图片

    Raises:
        ValueError: 不支持的图片格式或无法加载
    """
    # 已经是 PIL Image 对象
    if isinstance(source, Image.Image):
        return _ensure_rgb(source)

    # 字节数据
    if isinstance(source, bytes):
        return _load_from_bytes(source)

    # 路径或 URL
    source_str = str(source)

    if source_str.startswith(("http://", "https://")):
        return _load_from_url(source_str)
    else:
        return _load_from_file(source_str)


def compute_image_hash(image: Image.Image) -> str:
    """计算图片 MD5 哈希，用于缓存键"""
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    return hashlib.md5(img_bytes.getvalue()).hexdigest()


def validate_image(image: Image.Image) -> Tuple[bool, str]:
    """
    验证图片是否适合推理

    Returns:
        (是否有效, 错误信息)
    """
    if image is None:
        return False, "图片为空"
    if image.size[0] < 10 or image.size[1] < 10:
        return False, f"图片尺寸过小: {image.size}"
    if image.size[0] > 8000 or image.size[1] > 8000:
        return False, f"图片尺寸过大: {image.size}"
    return True, ""


# ------------------------------------------------------------------
# 内部函数
# ------------------------------------------------------------------

def _ensure_rgb(image: Image.Image) -> Image.Image:
    """确保图片为 RGB 格式"""
    if image.mode == "RGBA":
        # 创建白色背景，将 RGBA 合成到白色上
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background
    elif image.mode != "RGB":
        return image.convert("RGB")
    return image


def _load_from_file(path: str) -> Image.Image:
    """从本地文件加载图片"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在: {path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"不支持的图片格式: {path.suffix}，支持: {SUPPORTED_FORMATS}"
        )
    return _ensure_rgb(Image.open(path))


def _load_from_url(url: str, timeout: int = 10) -> Image.Image:
    """从 URL 加载图片"""
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        return _load_from_bytes(resp.content)
    except requests.RequestException as e:
        raise ValueError(f"下载图片失败: {url} - {e}")


def _load_from_bytes(data: bytes) -> Image.Image:
    """从字节数据加载图片"""
    return _ensure_rgb(Image.open(io.BytesIO(data)))


# 需要导入 Tuple（脚本顶部遗漏）
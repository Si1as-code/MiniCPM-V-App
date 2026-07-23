"""
============================================================================
结果解析器 - 将模型原始输出解析为结构化结果
============================================================================
技术栈: Python 标准库 (json, re, dataclasses)
输出的结构化结果供上层（数据库、UI、API 路由）直接使用
============================================================================
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """
    推理结果 - 统一数据类

    这是整个推理引擎的"出口"格式，下游模块（数据库、UI、API 路由）
    都从这个类读取数据。
    """

    # --- 核心字段 ---
    # 模型生成的原始文本
    raw_text: str = ""

    # 格式化的回答（去除特殊 token）
    formatted_text: str = ""

    # --- 元信息 ---
    # 模型来源: "on_device" / "cloud"
    model_source: str = "on_device"

    # 使用的模型名称
    model_name: str = ""

    # 推理耗时（秒）
    inference_time: float = 0.0

    # 置信度（0.0-1.0，基于生成概率估算）
    confidence: float = 0.0

    # --- 图片信息 ---
    # 图片哈希（用于缓存）
    image_hash: str = ""

    # 图片尺寸
    image_size: Optional[tuple] = None

    # --- 结构化提取（可选） ---
    # 识别到的物体标签
    labels: List[str] = field(default_factory=list)

    # 提取的文本（OCR 结果）
    extracted_text: str = ""

    # 原始 JSON 输出（如果模型输出 JSON）
    json_output: Optional[Dict[str, Any]] = None

    # --- 任务相关 ---
    # 任务类型: "describe" / "ocr" / "qa" / "classify" / "auto"
    task_type: str = "auto"

    # 用户原始问题
    user_question: str = ""

    # --- 时间戳 ---
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """转为字典（用于 JSON 序列化/数据库存储）"""
        return asdict(self)

    def to_json(self) -> str:
        """转为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def summary(self) -> str:
        """返回简短摘要"""
        return (
            f"[{self.model_source}] "
            f"{self.formatted_text[:100]}{'...' if len(self.formatted_text) > 100 else ''}"
            f" ({self.inference_time:.1f}s)"
        )


class ResultParser:
    """
    结果解析器

    将模型的原始文本输出解析为结构化的 InferenceResult。
    支持多种任务类型的特殊解析逻辑。
    """

    # 需要清理的特殊 token
    CLEANUP_PATTERNS = [
        (r"<\|im_start\|>", ""),
        (r"<\|im_end\|>", ""),
        (r"<\|endoftext\|>", ""),
        (r"<s>", ""),
        (r"</s>", ""),
        (r"<unk>", ""),
        (r"<pad>", ""),
        (r"<image>", ""),
        (r"<image_\d+>", ""),
    ]

    def parse(
        self,
        raw_text: str,
        model_name: str = "",
        inference_time: float = 0.0,
        model_source: str = "on_device",
        image_hash: str = "",
        image_size: Optional[tuple] = None,
        task_type: str = "auto",
        user_question: str = "",
    ) -> InferenceResult:
        """
        解析模型原始输出

        Args:
            raw_text: 模型原始输出文本
            model_name: 模型名称
            inference_time: 推理耗时
            model_source: 模型来源
            image_hash: 图片哈希
            image_size: 图片尺寸
            task_type: 任务类型
            user_question: 用户问题

        Returns:
            InferenceResult: 结构化的推理结果
        """
        # 1) 清理文本
        formatted = self._clean_text(raw_text)

        # 2) 估算置信度
        confidence = self._estimate_confidence(formatted, raw_text)

        # 3) 提取结构化信息
        labels = self._extract_labels(formatted)
        extracted_text = self._extract_ocr_text(formatted, raw_text)
        json_output = self._try_parse_json(formatted)

        result = InferenceResult(
            raw_text=raw_text,
            formatted_text=formatted,
            model_source=model_source,
            model_name=model_name,
            inference_time=inference_time,
            confidence=confidence,
            image_hash=image_hash,
            image_size=image_size,
            labels=labels,
            extracted_text=extracted_text,
            json_output=json_output,
            task_type=task_type,
            user_question=user_question,
        )

        logger.debug(f"解析结果: {result.summary()}")
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _clean_text(self, text: str) -> str:
        """清理特殊 token 和多余空白"""
        for pattern, replacement in self.CLEANUP_PATTERNS:
            text = re.sub(pattern, replacement, text)
        # 合并多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def _estimate_confidence(
        self, formatted_text: str, raw_text: str
    ) -> float:
        """估算置信度（简化版，基于文本特征）"""
        # 如果文本为空或过短，置信度低
        if not formatted_text or len(formatted_text) < 3:
            return 0.0

        # 如果包含"抱歉""无法"等拒绝词，置信度低
        refusal_patterns = [
            r"抱歉",
            r"无法",
            r"不能",
            r"不清楚",
            r"不确定",
            r"Sorry",
            r"cannot",
            r"unable",
        ]
        for pattern in refusal_patterns:
            if re.search(pattern, formatted_text):
                return 0.3

        # 正常输出，置信度较高
        return 0.85

    def _extract_labels(self, text: str) -> List[str]:
        """从文本中提取物体标签"""
        # 简单实现：提取引号内的内容、中文词汇等
        labels = []

        # 提取引号内的内容
        quoted = re.findall(r'"([^"]+)"', text)
        labels.extend(quoted)

        # 提取 "是" "这是" 后面的内容
        patterns = [
            r"这是[一]?(个|只|张|幅|辆|朵|棵|条|片|座|把|台|块|件|本|间|所|架|艘|匹|头|颗|粒|枚|根|支|顶|双|套|种|类)?(.+?)[。，,\.\n]",
            r"是[一]?(个|只|张|幅|辆|朵|棵|条|片|座|把|台|块|件|本|间|所|架|艘|匹|头|颗|粒|枚|根|支|顶|双|套|种|类)?(.+?)[。，,\.\n]",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                label = m[-1].strip() if isinstance(m, tuple) else m.strip()
                if len(label) > 2 and len(label) < 30:
                    labels.append(label)

        return labels[:10]  # 最多保留 10 个标签

    def _extract_ocr_text(
        self, formatted_text: str, raw_text: str
    ) -> str:
        """提取 OCR 文本"""
        # 如果回答中包含大量连续的非空白字符，可能是 OCR 结果
        # 简化实现：返回空，由模型输出直接作为 OCR 文本
        return ""

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试从文本中解析 JSON"""
        # 查找 JSON 块
        json_pattern = r"```json\s*(.*?)\s*```"
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试将整个文本作为 JSON 解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        return None


# 全局单例
result_parser = ResultParser()
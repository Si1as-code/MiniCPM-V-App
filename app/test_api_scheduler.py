"""
============================================================================
API 调度引擎 - 单元测试
============================================================================
用法:
    python test_api_scheduler.py

测试覆盖:
    - 配置加载与默认值
    - 预算控制逻辑
    - Provider 初始化
    - 路由决策逻辑（任务类型、置信度、强制模式）
    - 降级策略
    - 异步调度
============================================================================
"""

import sys
import time
from pathlib import Path

# 确保能找到 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

from api.config import (
    scheduler_config,
    SchedulerConfig,
    ProviderConfig,
    DEFAULT_PROVIDERS,
)
from api.budget import budget_controller
from api.router import SchedulerRouter, RouteDecision, scheduler_router
from api.fallback import fallback_handler, FallbackResult
from data import init_database, reset_database, settings_dao, usage_dao


def create_test_image() -> Image.Image:
    """创建测试用图片（4x4 像素，避免实际推理）"""
    return Image.new("RGB", (4, 4), color=(255, 0, 0))


def test_config_defaults():
    """测试配置默认值"""
    print("=" * 60)
    print("测试 1: 配置默认值")
    print("=" * 60)

    config = SchedulerConfig()
    assert config.cloud_confidence_threshold == 0.6
    assert config.force_local is False
    assert config.daily_budget == 0.0  # 0 = 不限制
    assert config.fallback_to_local_on_cloud_failure is True
    assert "qwen" in config.provider_priority
    assert "doubao" in config.provider_priority
    assert config.cloud_preferred_task_types == ["qa_complex", "ocr_high_accuracy"]
    assert config.local_forced_task_types == ["classify", "describe"]
    print("  默认配置正确")
    print("  通过")


def test_provider_config():
    """测试 Provider 配置"""
    print("\n" + "=" * 60)
    print("测试 2: Provider 配置")
    print("=" * 60)

    assert "qwen" in DEFAULT_PROVIDERS
    assert "doubao" in DEFAULT_PROVIDERS

    qwen = DEFAULT_PROVIDERS["qwen"]
    assert qwen.name == "qwen"
    assert qwen.display_name == "通义千问 VL"
    assert qwen.api_key_env == "QWEN_API_KEY"
    assert qwen.model_name == "qwen-vl-plus"
    assert qwen.cost_per_1k_tokens == 0.003
    assert qwen.enabled is False  # 默认未启用（需要用户配置 API Key）
    print(f"  Qwen Provider: {qwen.display_name}, 模型={qwen.model_name}, 成本={qwen.cost_per_1k_tokens}元/千token")
    print(f"  API Key 环境变量: {qwen.api_key_env}, 默认启用={qwen.enabled}")

    doubao = DEFAULT_PROVIDERS["doubao"]
    assert doubao.name == "doubao"
    assert doubao.display_name == "豆包视觉"
    assert doubao.cost_per_1k_tokens == 0.002
    print(f"  Doubao Provider: {doubao.display_name}, 模型={doubao.model_name}, 成本={doubao.cost_per_1k_tokens}元/千token")
    print("  通过")


def test_budget_control():
    """测试预算控制逻辑"""
    print("\n" + "=" * 60)
    print("测试 3: 预算控制")
    print("=" * 60)

    # 重置数据库
    reset_database()
    init_database()

    # 3.1 默认情况下云端 API 未开启 → 不可用
    can_use = budget_controller.can_use_cloud_api()
    assert can_use is False
    print("  3.1 云端 API 默认未开启: 正确")

    # 3.2 开启云端 API
    settings_dao.set_cloud_api_enabled(True)
    can_use = budget_controller.can_use_cloud_api()
    assert can_use is True  # 预算为0时表示不限制
    print("  3.2 开启云端 API 且预算无限制: 可用")

    # 3.3 设置预算上限
    settings_dao.set_daily_budget(0.1)  # 0.1 元
    can_use = budget_controller.can_use_cloud_api()
    assert can_use is True  # 还没花费
    print("  3.3 设置预算 0.1 元，未花费: 可用")

    # 3.4 记录费用使预算超限
    usage_dao.record_api_call(tokens=100000, cost=0.1)  # 花费 0.1 元
    can_use = budget_controller.can_use_cloud_api()
    assert can_use is False  # 预算已用完
    print("  3.4 预算超限: 不可用")

    # 3.5 预算状态查询
    status = budget_controller.get_budget_status()
    assert "budget" in status
    assert "today_cost" in status
    assert "can_use_cloud" in status
    assert "total_local" in status
    assert "total_api" in status
    print(f"  3.5 预算状态: {status}")

    # 3.6 记录端侧推理
    budget_controller.record_local_usage()
    status = budget_controller.get_budget_status()
    assert status["total_local"] >= 1
    print(f"  3.6 端侧统计: {status['total_local']}")

    print("  通过")


def test_route_by_task_type():
    """测试任务类型路由"""
    print("\n" + "=" * 60)
    print("测试 4: 任务类型路由")
    print("=" * 60)

    router = SchedulerRouter()

    # 4.1 强制端侧
    result = router._route_by_task_type(
        task_type="describe", force_local=True, force_cloud=False
    )
    assert result == "local"
    print("  4.1 强制端侧: 正确")

    # 4.2 强制云端
    result = router._route_by_task_type(
        task_type="describe", force_local=False, force_cloud=True
    )
    assert result == "cloud"
    print("  4.2 强制云端: 正确")

    # 4.3 端侧优先任务类型
    result = router._route_by_task_type(
        task_type="classify", force_local=False, force_cloud=False
    )
    assert result == "local"
    print("  4.3 端侧优先类型 (classify): 正确")

    result = router._route_by_task_type(
        task_type="describe", force_local=False, force_cloud=False
    )
    assert result == "local"
    print("  4.4 端侧优先类型 (describe): 正确")

    # 4.5 云端优先任务类型
    result = router._route_by_task_type(
        task_type="qa_complex", force_local=False, force_cloud=False
    )
    assert result == "cloud"
    print("  4.5 云端优先类型 (qa_complex): 正确")

    # 4.6 混合模式（默认）
    result = router._route_by_task_type(
        task_type="auto", force_local=False, force_cloud=False
    )
    assert result == "hybrid"
    print("  4.6 混合模式 (auto): 正确")

    print("  通过")


def test_force_local_mode():
    """测试强制端侧模式"""
    print("\n" + "=" * 60)
    print("测试 5: 强制端侧模式")
    print("=" * 60)

    # 设置 force_local
    scheduler_config.force_local = True

    # 预算检查应该返回 False
    can_use = budget_controller.can_use_cloud_api()
    assert can_use is False
    print("  5.1 force_local 模式下云端不可用: 正确")

    # 恢复
    scheduler_config.force_local = False
    print("  5.2 恢复后测试通过")
    print("  通过")


def test_provider_priority():
    """测试 Provider 优先级"""
    print("\n" + "=" * 60)
    print("测试 6: Provider 优先级")
    print("=" * 60)

    # 测试优先级顺序
    assert scheduler_config.provider_priority == ["qwen", "doubao"]
    print(f"  默认优先级: {scheduler_config.provider_priority}")

    # 测试首选 Provider 的优先级调整
    router = SchedulerRouter()
    available = router._get_available_providers(preferred="doubao")
    # 没有 API Key 的情况下，应该返回空列表
    assert isinstance(available, list)
    print(f"  无 API Key 时可用 Provider: {len(available)} 个")
    print("  通过")


def test_async_schedule():
    """测试异步调度"""
    print("\n" + "=" * 60)
    print("测试 7: 异步调度")
    print("=" * 60)

    task_id = scheduler_router.schedule_async(
        image_source="test.jpg",
        question="这是什么？",
        task_type="describe",
        provider="qwen",
    )
    assert task_id > 0
    print(f"  异步任务创建成功: id={task_id}")

    # 验证任务已写入数据库
    from data.dao_api_tasks import api_task_dao
    task = api_task_dao.get_by_id(task_id)
    assert task is not None
    assert task.provider == "qwen"
    assert task.status == "pending"
    print(f"  任务已在 api_tasks 表中: provider={task.provider}, status={task.status}")
    print("  通过")


def test_fallback_config():
    """测试降级策略配置"""
    print("\n" + "=" * 60)
    print("测试 8: 降级策略配置")
    print("=" * 60)

    assert scheduler_config.fallback_to_local_on_cloud_failure is True
    assert "请非常仔细地观察这张图片" in scheduler_config.fallback_retry_prompt
    print(f"  降级策略: 启用端侧重试")
    print(f"  重试 Prompt 长度: {len(scheduler_config.fallback_retry_prompt)} 字符")
    print("  通过")


def test_config_serialization():
    """测试配置序列化（环境变量覆盖）"""
    print("\n" + "=" * 60)
    print("测试 9: 环境变量覆盖")
    print("=" * 60)

    import os
    # 设置环境变量
    os.environ["CLOUD_CONFIDENCE_THRESHOLD"] = "0.8"
    os.environ["FORCE_LOCAL"] = "true"
    os.environ["DAILY_BUDGET"] = "0.5"

    # 重新创建配置（环境变量在实例化时读取）
    test_config = SchedulerConfig()
    assert test_config.cloud_confidence_threshold == 0.8
    assert test_config.force_local is True
    assert test_config.daily_budget == 0.5
    print(f"  环境变量 CLOUD_CONFIDENCE_THRESHOLD=0.8: {test_config.cloud_confidence_threshold}")
    print(f"  环境变量 FORCE_LOCAL=true: {test_config.force_local}")
    print(f"  环境变量 DAILY_BUDGET=0.5: {test_config.daily_budget}")

    # 清理
    del os.environ["CLOUD_CONFIDENCE_THRESHOLD"]
    del os.environ["FORCE_LOCAL"]
    del os.environ["DAILY_BUDGET"]
    print("  通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MiniCPM-V API 调度引擎 - 单元测试")
    print("=" * 60)

    test_count = 0
    passed = 0

    tests = [
        ("配置默认值", test_config_defaults),
        ("Provider 配置", test_provider_config),
        ("预算控制", test_budget_control),
        ("任务类型路由", test_route_by_task_type),
        ("强制端侧模式", test_force_local_mode),
        ("Provider 优先级", test_provider_priority),
        ("异步调度", test_async_schedule),
        ("降级策略配置", test_fallback_config),
        ("环境变量覆盖", test_config_serialization),
    ]

    for name, test_fn in tests:
        test_count += 1
        try:
            test_fn()
            passed += 1
            print(f"  ✅ {name}\n")
        except AssertionError as e:
            print(f"  ❌ {name} 失败: {e}\n")
        except Exception as e:
            print(f"  ❌ {name} 异常: {e}\n")
            import traceback
            traceback.print_exc()

    print("=" * 60)
    print(f"测试结果: {passed}/{test_count} 通过")
    print("=" * 60)

    if passed < test_count:
        print("❌ 部分测试失败")
        exit(1)
    else:
        print("✅ 全部通过!")


if __name__ == "__main__":
    run_all_tests()
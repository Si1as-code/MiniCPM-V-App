"""
============================================================================
数据持久层 - 单元测试
============================================================================
用法:
    python test_database.py
============================================================================
"""

import sys
import time
from pathlib import Path

# 确保能找到 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from data import (
    init_database,
    reset_database,
    recognition_dao,
    conversation_dao,
    api_task_dao,
    settings_dao,
    usage_dao,
    db_manager,
)
from data.models import (
    RecognitionRecord,
    Conversation,
    APITask,
    UserSetting,
    UsageStat,
)


def test_database_init():
    """测试数据库初始化"""
    print("=" * 60)
    print("测试 1: 数据库初始化")
    print("=" * 60)

    init_database()
    tables = [
        "schema_version",
        "recognition_records",
        "conversations",
        "image_index",
        "api_tasks",
        "user_settings",
        "usage_stats",
    ]
    for table in tables:
        exists = db_manager.table_exists(table)
        status = "OK" if exists else "FAIL"
        print(f"  表 {table}: {status}")
        assert exists, f"表 {table} 不存在"

    # 检查索引
    info = db_manager.get_table_info("recognition_records")
    print(f"  recognition_records 字段数: {len(info)}")
    print(f"  数据库路径: {db_manager.db_path}")
    print("  通过")


def test_recognition_dao():
    """测试识别记录 DAO"""
    print("\n" + "=" * 60)
    print("测试 2: 识别记录 DAO")
    print("=" * 60)

    # 插入
    record = RecognitionRecord(
        image_hash="abc123",
        image_path="/tmp/test.jpg",
        question="这是什么？",
        answer="这是一只猫。",
        confidence=0.92,
        model_version="MiniCPM-V-4.6",
        device_id="test_device",
        task_type="describe",
        synced=0,
    )
    rid = recognition_dao.insert(record)
    print(f"  插入记录 id={rid}")
    assert rid > 0

    # 查询
    fetched = recognition_dao.get_by_id(rid)
    assert fetched is not None
    assert fetched.answer == "这是一只猫。"
    assert fetched.confidence == 0.92
    print(f"  查询成功: confidence={fetched.confidence}")

    # 按 hash 查询
    by_hash = recognition_dao.get_by_hash("abc123")
    assert by_hash is not None
    assert by_hash.id == rid
    print(f"  按 hash 查询成功")

    # 更新
    fetched.confidence = 0.95
    rows = recognition_dao.update(fetched)
    assert rows == 1
    updated = recognition_dao.get_by_id(rid)
    assert updated.confidence == 0.95
    print(f"  更新成功: confidence={updated.confidence}")

    # 标记同步
    rows = recognition_dao.mark_synced(rid)
    assert rows == 1
    synced = recognition_dao.get_by_id(rid)
    assert synced.synced == 1
    print(f"  标记同步成功")

    # 统计
    stats = recognition_dao.get_stats()
    print(f"  统计: {stats}")
    assert stats["total"] >= 1

    # 删除
    rows = recognition_dao.delete(rid)
    assert rows == 1
    deleted = recognition_dao.get_by_id(rid)
    assert deleted is None
    print(f"  删除成功")
    print("  通过")


def test_conversation_dao():
    """测试多轮对话 DAO"""
    print("\n" + "=" * 60)
    print("测试 3: 多轮对话 DAO")
    print("=" * 60)

    # 先插入一条识别记录作为外键
    record = RecognitionRecord(
        image_hash="conv_test",
        question="描述图片",
        answer="描述结果",
        confidence=0.8,
    )
    rid = recognition_dao.insert(record)

    # 插入对话
    c1 = Conversation(record_id=rid, role="user", content="图中有几只猫？")
    c2 = Conversation(record_id=rid, role="assistant", content="有 3 只猫。")
    id1 = conversation_dao.insert(c1)
    id2 = conversation_dao.insert(c2)
    print(f"  插入对话 id={id1}, {id2}")

    # 按 record_id 查询
    convs = conversation_dao.get_by_record_id(rid)
    assert len(convs) == 2
    print(f"  查询到 {len(convs)} 条对话")

    # token 统计
    token_sum = conversation_dao.get_token_sum_by_record(rid)
    print(f"  token 总数: {token_sum}")

    # 删除
    conversation_dao.delete_by_record_id(rid)
    convs = conversation_dao.get_by_record_id(rid)
    assert len(convs) == 0
    print(f"  删除成功")

    # 清理父记录
    recognition_dao.delete(rid)
    print("  通过")


def test_api_task_dao():
    """测试 API 任务队列 DAO"""
    print("\n" + "=" * 60)
    print("测试 4: API 任务队列 DAO")
    print("=" * 60)

    task = APITask(
        record_id=1,
        provider="qwen",
        status="pending",
        scheduled_at=time.time(),
    )
    tid = api_task_dao.insert(task)
    print(f"  插入任务 id={tid}")

    # 查询待执行
    pending = api_task_dao.get_pending()
    assert len(pending) >= 1
    print(f"  待执行任务数: {len(pending)}")

    # 更新状态
    api_task_dao.update_status(tid, "running")
    running = api_task_dao.get_by_status("running")
    assert any(t.id == tid for t in running)
    print(f"  状态更新成功")

    # 标记完成
    api_task_dao.update_status(tid, "completed")
    completed = api_task_dao.get_by_status("completed")
    assert any(t.id == tid for t in completed)
    print(f"  完成标记成功")

    # 清理
    api_task_dao.delete(tid)
    print("  通过")


def test_settings_dao():
    """测试用户设置 DAO"""
    print("\n" + "=" * 60)
    print("测试 5: 用户设置 DAO")
    print("=" * 60)

    # 设置各种类型
    settings_dao.set("test_string", "hello")
    settings_dao.set("test_int", 42)
    settings_dao.set("test_float", 3.14)
    settings_dao.set("test_bool", True)
    settings_dao.set("test_dict", {"a": 1, "b": [2, 3]})
    print("  插入 5 条设置")

    # 读取
    assert settings_dao.get("test_string") == "hello"
    assert settings_dao.get("test_int") == 42
    assert settings_dao.get("test_float") == 3.14
    assert settings_dao.get("test_bool") is True
    assert settings_dao.get("test_dict") == {"a": 1, "b": [2, 3]}
    print("  读取正确")

    # 类型快捷方法
    assert settings_dao.get_bool("test_bool") is True
    assert settings_dao.get_int("test_int") == 42
    assert settings_dao.get_float("test_float") == 3.14
    print("  类型快捷方法通过")

    # 默认值
    assert settings_dao.get("not_exist", "default") == "default"
    assert settings_dao.get_bool("not_exist", False) is False
    print("  默认值通过")

    # 获取所有
    all_settings = settings_dao.get_all()
    assert "test_string" in all_settings
    print(f"  获取所有设置: {len(all_settings)} 条")

    # 快捷方法
    settings_dao.set_auto_recognition(True)
    assert settings_dao.get_auto_recognition() is True
    settings_dao.set_cloud_api_enabled(True)
    assert settings_dao.get_cloud_api_enabled() is True
    settings_dao.set_daily_budget(10.0)
    assert settings_dao.get_daily_budget() == 10.0
    print("  预设快捷方法通过")

    # 清理
    for key in ["test_string", "test_int", "test_float", "test_bool", "test_dict",
                "auto_recognition", "cloud_api_enabled", "daily_budget"]:
        settings_dao.delete(key)
    print("  通过")


def test_usage_dao():
    """测试使用统计 DAO"""
    print("\n" + "=" * 60)
    print("测试 6: 使用统计 DAO")
    print("=" * 60)

    # 记录端侧推理
    usage_dao.record_local_inference(tokens=100)
    usage_dao.record_local_inference(tokens=200)
    print("  记录 2 次端侧推理")

    # 记录 API 调用
    usage_dao.record_api_call(tokens=500, cost=0.05)
    print("  记录 1 次 API 调用")

    # 查询今天
    today = usage_dao.get_today()
    assert today is not None
    assert today.local_count == 2
    assert today.api_count == 1
    assert today.tokens_used == 800
    print(f"  今日统计: local={today.local_count}, api={today.api_count}, tokens={today.tokens_used}")

    # 累计统计
    total = usage_dao.get_total_stats()
    print(f"  累计统计: {total}")
    assert total["total_local"] >= 2
    assert total["total_api"] >= 1

    # 预算检查
    budget_info = usage_dao.get_daily_budget_usage(budget=1.0)
    print(f"  预算使用: {budget_info}")

    # 最近7天
    last7 = usage_dao.get_last_n_days(7)
    print(f"  最近7天记录数: {len(last7)}")
    print("  通过")


def test_transaction():
    """测试事务管理"""
    print("\n" + "=" * 60)
    print("测试 7: 事务管理")
    print("=" * 60)

    initial_count = recognition_dao.count()

    try:
        with db_manager.transaction():
            r1 = RecognitionRecord(image_hash="tx1", question="q1", answer="a1")
            r2 = RecognitionRecord(image_hash="tx2", question="q2", answer="a2")
            recognition_dao.insert(r1)
            recognition_dao.insert(r2)
            # 模拟错误，应该回滚
            raise ValueError("模拟错误")
    except ValueError:
        pass

    # 验证回滚
    after_count = recognition_dao.count()
    assert after_count == initial_count, "事务回滚失败"
    print(f"  事务回滚成功: {initial_count} == {after_count}")

    # 正常事务提交
    with db_manager.transaction():
        r = RecognitionRecord(image_hash="tx_ok", question="q_ok", answer="a_ok")
        recognition_dao.insert(r)

    after_count2 = recognition_dao.count()
    assert after_count2 == initial_count + 1
    print(f"  事务提交成功")
    print("  通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MiniCPM-V 数据持久层 - 单元测试")
    print("=" * 60)

    try:
        # 重置数据库（干净环境）
        reset_database()

        test_database_init()
        test_recognition_dao()
        test_conversation_dao()
        test_api_task_dao()
        test_settings_dao()
        test_usage_dao()
        test_transaction()

        print("\n" + "=" * 60)
        print("所有测试通过!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()

"""数据库操作测试

测试内容：
- Task 模型的 CRUD 操作
- 多租户数据库隔离
- LedgerRecord 操作
"""
import pytest
import os
import sys
import tempfile
import shutil
from datetime import datetime, date
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# 测试用户配置
TEST_USER_1 = "test_user_1"
TEST_USER_2 = "test_user_2"


@pytest.fixture(autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 创建临时数据目录
    temp_dir = tempfile.mkdtemp()
    test_data_dir = Path(temp_dir) / "data"

    # 保存原始路径
    import lingxi_qwenpaw.db as db_module
    original_data_dir = db_module.DATA_DIR
    original_db_dir = db_module.DB_DIR

    # 设置测试数据目录
    db_module.DATA_DIR = test_data_dir
    db_module.DB_DIR = test_data_dir / "user_data"

    # 清空引擎缓存
    db_module._engines.clear()
    db_module._SessionLocals.clear()

    yield test_data_dir

    # 清理临时目录
    db_module.DATA_DIR = original_data_dir
    db_module.DB_DIR = original_db_dir
    db_module._engines.clear()
    db_module._SessionLocals.clear()
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestTaskCRUD:
    """Task 模型 CRUD 操作测试"""

    def test_create_task(self, setup_test_environment):
        """测试创建任务"""
        from lingxi_qwenpaw.db import get_session, Task, set_current_user

        set_current_user(TEST_USER_1)

        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="测试任务内容",
                urgency=3,
                status="pending"
            )
            sess.add(task)
            sess.commit()

            # 验证任务已创建
            saved_task = sess.query(Task).filter(Task.user_id == TEST_USER_1).first()
            assert saved_task is not None
            assert saved_task.content == "测试任务内容"
            assert saved_task.urgency == 3
            assert saved_task.status == "pending"

    def test_read_task(self, setup_test_environment):
        """测试读取任务"""
        from lingxi_qwenpaw.db import get_session, Task

        # 先创建任务
        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="读取测试任务",
                urgency=2
            )
            sess.add(task)
            sess.commit()
            task_id = task.id

        # 读取任务
        with get_session(TEST_USER_1) as sess:
            found_task = sess.query(Task).filter(Task.id == task_id).first()
            assert found_task is not None
            assert found_task.content == "读取测试任务"

    def test_update_task(self, setup_test_environment):
        """测试更新任务"""
        from lingxi_qwenpaw.db import get_session, Task

        # 创建任务
        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="更新前内容",
                status="pending"
            )
            sess.add(task)
            sess.commit()
            task_id = task.id

        # 更新任务
        with get_session(TEST_USER_1) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            task.content = "更新后内容"
            task.status = "done"
            task.done_at = datetime.utcnow()
            sess.commit()

        # 验证更新
        with get_session(TEST_USER_1) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            assert task.content == "更新后内容"
            assert task.status == "done"
            assert task.done_at is not None

    def test_delete_task(self, setup_test_environment):
        """测试删除任务"""
        from lingxi_qwenpaw.db import get_session, Task

        # 创建任务
        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="待删除任务"
            )
            sess.add(task)
            sess.commit()
            task_id = task.id

        # 删除任务
        with get_session(TEST_USER_1) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            sess.delete(task)
            sess.commit()

        # 验证删除
        with get_session(TEST_USER_1) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            assert task is None

    def test_list_tasks(self, setup_test_environment):
        """测试列出任务"""
        from lingxi_qwenpaw.db import get_session, Task

        # 创建多个任务
        with get_session(TEST_USER_1) as sess:
            for i in range(5):
                task = Task(
                    user_id=TEST_USER_1,
                    content=f"任务 {i + 1}",
                    urgency=i % 3 + 1,
                    status="pending" if i < 3 else "done"
                )
                sess.add(task)
            sess.commit()

        # 列出待办任务
        with get_session(TEST_USER_1) as sess:
            pending_tasks = sess.query(Task).filter(
                Task.user_id == TEST_USER_1,
                Task.status == "pending"
            ).all()
            assert len(pending_tasks) == 3

    def test_task_with_deadline(self, setup_test_environment):
        """测试带截止日期的任务"""
        from lingxi_qwenpaw.db import get_session, Task

        deadline = date.today().isoformat()

        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="有截止日期的任务",
                deadline=deadline
            )
            sess.add(task)
            sess.commit()

            saved_task = sess.query(Task).filter(
                Task.user_id == TEST_USER_1,
                Task.content == "有截止日期的任务"
            ).first()
            assert saved_task.deadline == deadline

    def test_task_with_tags(self, setup_test_environment):
        """测试带标签的任务"""
        from lingxi_qwenpaw.db import get_session, Task

        tags = ["学习", "重要", "紧急"]

        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="带标签的任务",
                tags=tags
            )
            sess.add(task)
            sess.commit()

            saved_task = sess.query(Task).filter(
                Task.user_id == TEST_USER_1,
                Task.content == "带标签的任务"
            ).first()
            assert saved_task.tags == tags


class TestMultiTenantIsolation:
    """多租户数据库隔离测试"""

    def test_separate_databases(self, setup_test_environment):
        """测试不同用户使用不同数据库"""
        from lingxi_qwenpaw.db import get_session, Task, get_db_path

        # 用户1创建任务
        with get_session(TEST_USER_1) as sess:
            task = Task(user_id=TEST_USER_1, content="用户1的任务")
            sess.add(task)
            sess.commit()

        # 用户2创建任务
        with get_session(TEST_USER_2) as sess:
            task = Task(user_id=TEST_USER_2, content="用户2的任务")
            sess.add(task)
            sess.commit()

        # 验证数据库路径不同
        db_path_1 = get_db_path(TEST_USER_1)
        db_path_2 = get_db_path(TEST_USER_2)
        assert db_path_1 != db_path_2
        assert db_path_1.exists()
        assert db_path_2.exists()

    def test_data_isolation(self, setup_test_environment):
        """测试数据隔离"""
        from lingxi_qwenpaw.db import get_session, Task

        # 用户1创建任务
        with get_session(TEST_USER_1) as sess:
            task = Task(user_id=TEST_USER_1, content="用户1的私密任务")
            sess.add(task)
            sess.commit()

        # 用户2不应该能看到用户1的任务
        with get_session(TEST_USER_2) as sess:
            tasks = sess.query(Task).filter(Task.user_id == TEST_USER_1).all()
            assert len(tasks) == 0

        # 用户1应该能看到自己的任务
        with get_session(TEST_USER_1) as sess:
            tasks = sess.query(Task).filter(Task.user_id == TEST_USER_1).all()
            assert len(tasks) == 1
            assert tasks[0].content == "用户1的私密任务"

    def test_cross_user_operations(self, setup_test_environment):
        """测试跨用户操作"""
        from lingxi_qwenpaw.db import get_session, Task

        # 两个用户各自创建任务
        with get_session(TEST_USER_1) as sess:
            task1 = Task(user_id=TEST_USER_1, content="用户1任务")
            sess.add(task1)
            sess.commit()
            task1_id = task1.id

        with get_session(TEST_USER_2) as sess:
            task2 = Task(user_id=TEST_USER_2, content="用户2任务")
            sess.add(task2)
            sess.commit()
            task2_id = task2.id

        # 验证 ID 可以相同（不同数据库）
        # 但各自数据库中是独立的

        with get_session(TEST_USER_1) as sess:
            task = sess.query(Task).filter(Task.id == task1_id).first()
            assert task is not None
            assert task.content == "用户1任务"

        with get_session(TEST_USER_2) as sess:
            task = sess.query(Task).filter(Task.id == task2_id).first()
            assert task is not None
            assert task.content == "用户2任务"


class TestLedgerRecord:
    """LedgerRecord 操作测试"""

    def test_create_income_record(self, setup_test_environment):
        """测试创建收入记录"""
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        with get_session(TEST_USER_1) as sess:
            record = LedgerRecord(
                user_id=TEST_USER_1,
                record_type="income",
                amount=1000.0,
                category="工资",
                note="月工资",
                date=date.today().isoformat()
            )
            sess.add(record)
            sess.commit()

            saved = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER_1
            ).first()
            assert saved is not None
            assert saved.record_type == "income"
            assert saved.amount == 1000.0

    def test_create_expense_record(self, setup_test_environment):
        """测试创建支出记录"""
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        with get_session(TEST_USER_1) as sess:
            record = LedgerRecord(
                user_id=TEST_USER_1,
                record_type="expense",
                amount=50.0,
                category="餐饮",
                note="午餐",
                date=date.today().isoformat()
            )
            sess.add(record)
            sess.commit()

            saved = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER_1
            ).first()
            assert saved.record_type == "expense"
            assert saved.amount == 50.0

    def test_monthly_summary(self, setup_test_environment):
        """测试月度汇总"""
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        today = date.today()
        month_str = today.strftime("%Y-%m")

        with get_session(TEST_USER_1) as sess:
            # 添加收入
            for _ in range(3):
                record = LedgerRecord(
                    user_id=TEST_USER_1,
                    record_type="income",
                    amount=1000.0,
                    category="工资",
                    date=today.isoformat()
                )
                sess.add(record)

            # 添加支出
            for _ in range(5):
                record = LedgerRecord(
                    user_id=TEST_USER_1,
                    record_type="expense",
                    amount=100.0,
                    category="餐饮",
                    date=today.isoformat()
                )
                sess.add(record)

            sess.commit()

            # 计算汇总
            records = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER_1,
                LedgerRecord.date.startswith(month_str)
            ).all()

            income = sum(r.amount for r in records if r.record_type == "income")
            expense = sum(r.amount for r in records if r.record_type == "expense")

            assert income == 3000.0
            assert expense == 500.0
            assert income - expense == 2500.0

    def test_ledger_isolation(self, setup_test_environment):
        """测试账本数据隔离"""
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        # 用户1添加记录
        with get_session(TEST_USER_1) as sess:
            record = LedgerRecord(
                user_id=TEST_USER_1,
                record_type="expense",
                amount=100.0,
                category="测试",
                date=date.today().isoformat()
            )
            sess.add(record)
            sess.commit()

        # 用户2不应该能看到用户1的记录
        with get_session(TEST_USER_2) as sess:
            records = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER_1
            ).all()
            assert len(records) == 0


class TestOtherModels:
    """其他模型测试"""

    def test_time_log(self, setup_test_environment):
        """测试时间记录"""
        from lingxi_qwenpaw.db import get_session, TimeLog

        with get_session(TEST_USER_1) as sess:
            log = TimeLog(
                user_id=TEST_USER_1,
                category="学习",
                minutes=120,
                note="复习数学",
                date=date.today().isoformat()
            )
            sess.add(log)
            sess.commit()

            saved = sess.query(TimeLog).filter(
                TimeLog.user_id == TEST_USER_1
            ).first()
            assert saved.minutes == 120

    def test_journal_entry(self, setup_test_environment):
        """测试日记条目"""
        from lingxi_qwenpaw.db import get_session, JournalEntry

        with get_session(TEST_USER_1) as sess:
            entry = JournalEntry(
                user_id=TEST_USER_1,
                date=date.today().isoformat(),
                text="今天天气很好，心情不错。"
            )
            sess.add(entry)
            sess.commit()

            saved = sess.query(JournalEntry).filter(
                JournalEntry.user_id == TEST_USER_1
            ).first()
            assert "天气很好" in saved.text

    def test_user_profile(self, setup_test_environment):
        """测试用户配置"""
        from lingxi_qwenpaw.db import get_session, UserProfile

        with get_session(TEST_USER_1) as sess:
            profile = UserProfile(
                user_id=TEST_USER_1,
                learning_style="visual",
                stress_level=3,
                current_goals=["学习Python", "锻炼身体"]
            )
            sess.add(profile)
            sess.commit()

            saved = sess.query(UserProfile).filter(
                UserProfile.user_id == TEST_USER_1
            ).first()
            assert saved.learning_style == "visual"
            assert "学习Python" in saved.current_goals

    def test_memory_entry(self, setup_test_environment):
        """测试记忆条目"""
        from lingxi_qwenpaw.db import get_session, MemoryEntry

        with get_session(TEST_USER_1) as sess:
            entry = MemoryEntry(
                user_id=TEST_USER_1,
                layer="observation",
                content="用户今天心情不错",
                importance=7
            )
            sess.add(entry)
            sess.commit()

            saved = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == TEST_USER_1
            ).first()
            assert saved.layer == "observation"
            assert saved.importance == 7

    def test_social_post(self, setup_test_environment):
        """测试社交帖子"""
        from lingxi_qwenpaw.db import get_session, SocialPost

        with get_session(TEST_USER_1) as sess:
            post = SocialPost(
                user_id=TEST_USER_1,
                author_id="lingxi",
                author_name="灵犀",
                content="今天是个好日子",
                post_type="daily_life"
            )
            sess.add(post)
            sess.commit()

            saved = sess.query(SocialPost).filter(
                SocialPost.user_id == TEST_USER_1
            ).first()
            assert saved.author_name == "灵犀"
            assert saved.post_type == "daily_life"


class TestDatabaseUtilities:
    """数据库工具函数测试"""

    def test_set_current_user(self, setup_test_environment):
        """测试设置当前用户"""
        from lingxi_qwenpaw.db import set_current_user, get_current_user_id

        set_current_user(TEST_USER_1)
        assert get_current_user_id() == TEST_USER_1

        set_current_user(TEST_USER_2)
        assert get_current_user_id() == TEST_USER_2

    def test_get_db_path(self, setup_test_environment):
        """测试获取数据库路径"""
        from lingxi_qwenpaw.db import get_db_path

        path = get_db_path(TEST_USER_1)
        assert str(path).endswith("lingxi.db")
        assert TEST_USER_1 in str(path)

    def test_task_to_dict(self, setup_test_environment):
        """测试任务转字典"""
        from lingxi_qwenpaw.db import get_session, Task, task_to_dict

        with get_session(TEST_USER_1) as sess:
            task = Task(
                user_id=TEST_USER_1,
                content="测试任务",
                urgency=3,
                status="pending"
            )
            sess.add(task)
            sess.commit()

            task_dict = task_to_dict(task)
            assert task_dict["content"] == "测试任务"
            assert task_dict["urgency"] == 3
            assert task_dict["status"] == "pending"

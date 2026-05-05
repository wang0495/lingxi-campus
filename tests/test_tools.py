"""工具函数测试

测试内容：
- create_task 工具
- add_ledger 工具
- get_emotion_status 工具
"""
import pytest
import os
import sys
import tempfile
import shutil
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# 测试用户配置
TEST_USER = "test"


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


class TestCreateTaskTool:
    """create_task 工具测试"""

    @pytest.mark.asyncio
    async def test_create_task_basic(self, setup_test_environment):
        """测试基本任务创建"""
        from lingxi_qwenpaw.tools import create_task
        from lingxi_qwenpaw.db import get_session, Task

        result = await create_task(
            content="测试任务",
            urgency=3,
            user_id=TEST_USER
        )

        assert result["success"] is True
        assert "已创建任务" in result["content"]

        # 验证数据库中的任务
        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "测试任务"
            ).first()
            assert task is not None
            assert task.urgency == 3

    @pytest.mark.asyncio
    async def test_create_task_with_deadline(self, setup_test_environment):
        """测试带截止日期的任务创建"""
        from lingxi_qwenpaw.tools import create_task
        from lingxi_qwenpaw.db import get_session, Task

        deadline = date.today().isoformat()

        result = await create_task(
            content="有截止日期的任务",
            urgency=5,
            deadline=deadline,
            user_id=TEST_USER
        )

        assert result["success"] is True

        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "有截止日期的任务"
            ).first()
            assert task.deadline == deadline

    @pytest.mark.asyncio
    async def test_create_task_with_chinese_deadline(self, setup_test_environment):
        """测试中文截止日期解析"""
        from lingxi_qwenpaw.tools import create_task, _normalize_deadline

        # 测试"明天"
        result = _normalize_deadline("明天")
        expected = (date.today() + timedelta(days=1)).isoformat()
        assert result == expected

        # 测试"后天"
        result = _normalize_deadline("后天")
        expected = (date.today() + timedelta(days=2)).isoformat()
        assert result == expected

        # 测试"今天"
        result = _normalize_deadline("今天")
        expected = date.today().isoformat()
        assert result == expected

    @pytest.mark.asyncio
    async def test_create_task_with_tags(self, setup_test_environment):
        """测试带标签的任务创建"""
        from lingxi_qwenpaw.tools import create_task
        from lingxi_qwenpaw.db import get_session, Task
        import json

        tags = ["学习", "重要"]
        tags_json = json.dumps(tags)

        result = await create_task(
            content="带标签的任务",
            tags_json=tags_json,
            user_id=TEST_USER
        )

        assert result["success"] is True

        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "带标签的任务"
            ).first()
            assert task.tags == tags

    @pytest.mark.asyncio
    async def test_create_task_with_effort(self, setup_test_environment):
        """测试带工作量的任务创建"""
        from lingxi_qwenpaw.tools import create_task
        from lingxi_qwenpaw.db import get_session, Task

        result = await create_task(
            content="大工作量任务",
            effort="high",
            user_id=TEST_USER
        )

        assert result["success"] is True

        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "大工作量任务"
            ).first()
            assert task.effort == "high"


class TestListTasksTool:
    """list_tasks 工具测试"""

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, setup_test_environment):
        """测试空任务列表"""
        from lingxi_qwenpaw.tools import list_tasks

        result = await list_tasks(user_id=TEST_USER)

        assert result["success"] is True
        assert "没有任务" in result["content"]

    @pytest.mark.asyncio
    async def test_list_tasks_with_data(self, setup_test_environment):
        """测试有数据的任务列表"""
        from lingxi_qwenpaw.tools import list_tasks, create_task

        # 创建几个任务
        await create_task("任务1", urgency=3, user_id=TEST_USER)
        await create_task("任务2", urgency=5, user_id=TEST_USER)
        await create_task("任务3", urgency=1, user_id=TEST_USER)

        result = await list_tasks(user_id=TEST_USER)

        assert result["success"] is True
        assert "任务1" in result["content"]
        assert "任务2" in result["content"]
        assert "任务3" in result["content"]

    @pytest.mark.asyncio
    async def test_list_tasks_filter_status(self, setup_test_environment):
        """测试按状态过滤任务"""
        from lingxi_qwenpaw.tools import list_tasks, create_task, complete_task
        from lingxi_qwenpaw.db import get_session, Task

        # 创建任务
        result1 = await create_task("待办任务", user_id=TEST_USER)
        result2 = await create_task("已完成任务", user_id=TEST_USER)

        # 获取任务 ID
        with get_session(TEST_USER) as sess:
            task2 = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "已完成任务"
            ).first()
            if task2:
                await complete_task(task2.id, user_id=TEST_USER)

        # 过滤待办任务
        result = await list_tasks(status="pending", user_id=TEST_USER)

        assert result["success"] is True
        assert "待办任务" in result["content"]


class TestCompleteTaskTool:
    """complete_task 工具测试"""

    @pytest.mark.asyncio
    async def test_complete_task_success(self, setup_test_environment):
        """测试成功完成任务"""
        from lingxi_qwenpaw.tools import create_task, complete_task
        from lingxi_qwenpaw.db import get_session, Task

        # 创建任务
        await create_task("待完成任务", user_id=TEST_USER)

        # 获取任务 ID
        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "待完成任务"
            ).first()
            task_id = task.id

        # 完成任务
        result = await complete_task(task_id, user_id=TEST_USER)

        assert result["success"] is True
        assert "已完成" in result["content"]

        # 验证状态
        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            assert task.status == "done"
            assert task.done_at is not None

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self, setup_test_environment):
        """测试完成不存在的任务"""
        from lingxi_qwenpaw.tools import complete_task

        result = await complete_task(99999, user_id=TEST_USER)

        assert result["success"] is False
        assert "不存在" in result["content"]


class TestAddLedgerTool:
    """add_ledger 工具测试"""

    @pytest.mark.asyncio
    async def test_add_income(self, setup_test_environment):
        """测试添加收入"""
        from lingxi_qwenpaw.tools import add_ledger
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        result = await add_ledger(
            record_type="income",
            amount=1000.0,
            category="工资",
            note="月工资",
            user_id=TEST_USER
        )

        assert result["success"] is True
        assert "已记账" in result["content"]
        assert "income" in result["content"]

        # 验证数据库
        with get_session(TEST_USER) as sess:
            record = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER
            ).first()
            assert record.record_type == "income"
            assert record.amount == 1000.0

    @pytest.mark.asyncio
    async def test_add_expense(self, setup_test_environment):
        """测试添加支出"""
        from lingxi_qwenpaw.tools import add_ledger
        from lingxi_qwenpaw.db import get_session, LedgerRecord

        result = await add_ledger(
            record_type="expense",
            amount=50.0,
            category="餐饮",
            note="午餐",
            user_id=TEST_USER
        )

        assert result["success"] is True
        assert "expense" in result["content"]

        with get_session(TEST_USER) as sess:
            record = sess.query(LedgerRecord).filter(
                LedgerRecord.user_id == TEST_USER,
                LedgerRecord.category == "餐饮"
            ).first()
            assert record.amount == 50.0

    @pytest.mark.asyncio
    async def test_get_ledger_summary(self, setup_test_environment):
        """测试获取账本汇总"""
        from lingxi_qwenpaw.tools import add_ledger, get_ledger_summary

        # 添加收入和支出
        await add_ledger("income", 2000.0, "工资", user_id=TEST_USER)
        await add_ledger("expense", 100.0, "餐饮", user_id=TEST_USER)
        await add_ledger("expense", 200.0, "交通", user_id=TEST_USER)

        result = await get_ledger_summary(user_id=TEST_USER)

        assert result["success"] is True
        assert "收入" in result["content"]
        assert "支出" in result["content"]
        assert "结余" in result["content"]


class TestGetEmotionStatusTool:
    """get_emotion_status 工具测试"""

    @pytest.mark.asyncio
    async def test_get_emotion_status(self, setup_test_environment):
        """测试获取情绪状态"""
        from lingxi_qwenpaw.tools import get_emotion_status

        result = await get_emotion_status(user_id=TEST_USER)

        assert result["success"] is True
        # 情绪状态应该是 JSON 格式
        import json
        state = json.loads(result["content"])
        assert "emotion" in state
        assert "intensity" in state
        assert "emoji" in state

    @pytest.mark.asyncio
    async def test_get_emotion_status_structure(self, setup_test_environment):
        """测试情绪状态结构"""
        from lingxi_qwenpaw.tools import get_emotion_status
        import json

        result = await get_emotion_status(user_id=TEST_USER)
        state = json.loads(result["content"])

        # 验证必要字段
        required_fields = ["emotion", "intensity", "emoji", "label", "is_grumpy", "is_shy"]
        for field in required_fields:
            assert field in state, f"缺少字段: {field}"


class TestOnUserComplimentTool:
    """on_user_compliment 工具测试"""

    @pytest.mark.asyncio
    async def test_user_compliment(self, setup_test_environment):
        """测试用户夸奖"""
        from lingxi_qwenpaw.tools import on_user_compliment

        result = await on_user_compliment(user_id=TEST_USER)

        assert result["success"] is True
        assert "开心" in result["content"] or "害羞" in result["content"]


class TestOnUserApologizeTool:
    """on_user_apologize 工具测试"""

    @pytest.mark.asyncio
    async def test_user_apologize(self, setup_test_environment):
        """测试用户道歉"""
        from lingxi_qwenpaw.tools import on_user_apologize

        result = await on_user_apologize(user_id=TEST_USER)

        assert result["success"] is True
        assert "原谅" in result["content"] or "解除" in result["content"]


class TestOnUserIgnoreTool:
    """on_user_ignore 工具测试"""

    @pytest.mark.asyncio
    async def test_user_ignore(self, setup_test_environment):
        """测试用户忽略"""
        from lingxi_qwenpaw.tools import on_user_ignore

        result = await on_user_ignore(user_id=TEST_USER)

        assert result["success"] is True
        # 第一次忽略可能不会触发傲娇
        assert result["content"] is not None


class TestGetLifeStatusTool:
    """get_life_status 工具测试"""

    @pytest.mark.asyncio
    async def test_get_life_status(self, setup_test_environment):
        """测试获取生命状态"""
        from lingxi_qwenpaw.tools import get_life_status

        result = await get_life_status(user_id=TEST_USER)

        assert result["success"] is True
        import json
        state = json.loads(result["content"])
        assert "energy" in state
        assert "mood" in state

    @pytest.mark.asyncio
    async def test_get_life_status_values(self, setup_test_environment):
        """测试生命状态值范围"""
        from lingxi_qwenpaw.tools import get_life_status
        import json

        result = await get_life_status(user_id=TEST_USER)
        state = json.loads(result["content"])

        # 验证值范围
        assert 0 <= state["energy"] <= 100
        assert -5 <= state["mood"] <= 5
        assert 0 <= state["curiosity"] <= 100
        assert 0 <= state["social_need"] <= 100


class TestTimeLogTools:
    """时间记录工具测试"""

    @pytest.mark.asyncio
    async def test_log_time(self, setup_test_environment):
        """测试记录时间"""
        from lingxi_qwenpaw.tools import log_time
        from lingxi_qwenpaw.db import get_session, TimeLog

        result = await log_time(
            category="学习",
            minutes=120,
            note="复习数学",
            user_id=TEST_USER
        )

        assert result["success"] is True
        assert "已记录" in result["content"]

        with get_session(TEST_USER) as sess:
            log = sess.query(TimeLog).filter(
                TimeLog.user_id == TEST_USER
            ).first()
            assert log.minutes == 120

    @pytest.mark.asyncio
    async def test_get_time_summary(self, setup_test_environment):
        """测试获取时间汇总"""
        from lingxi_qwenpaw.tools import log_time, get_time_summary

        # 记录一些时间
        await log_time("学习", 60, user_id=TEST_USER)
        await log_time("运动", 30, user_id=TEST_USER)
        await log_time("学习", 90, user_id=TEST_USER)

        result = await get_time_summary(days=7, user_id=TEST_USER)

        assert result["success"] is True
        assert "学习" in result["content"]
        assert "合计" in result["content"]


class TestJournalTools:
    """日记工具测试"""

    @pytest.mark.asyncio
    async def test_add_journal(self, setup_test_environment):
        """测试添加日记"""
        from lingxi_qwenpaw.tools import add_journal
        from lingxi_qwenpaw.db import get_session, JournalEntry

        result = await add_journal(
            text="今天天气很好，心情不错。",
            user_id=TEST_USER
        )

        assert result["success"] is True
        assert "日记已保存" in result["content"]

        with get_session(TEST_USER) as sess:
            entry = sess.query(JournalEntry).filter(
                JournalEntry.user_id == TEST_USER
            ).first()
            assert "天气很好" in entry.text

    @pytest.mark.asyncio
    async def test_get_journals(self, setup_test_environment):
        """测试获取日记"""
        from lingxi_qwenpaw.tools import add_journal, get_journals

        await add_journal("日记1", user_id=TEST_USER)
        await add_journal("日记2", user_id=TEST_USER)

        result = await get_journals(user_id=TEST_USER)

        assert result["success"] is True


class TestDeferTaskTool:
    """defer_task 工具测试"""

    @pytest.mark.asyncio
    async def test_defer_task(self, setup_test_environment):
        """测试推迟任务"""
        from lingxi_qwenpaw.tools import create_task, defer_task
        from lingxi_qwenpaw.db import get_session, Task

        # 创建任务
        await create_task("待推迟任务", deadline=date.today().isoformat(), user_id=TEST_USER)

        # 获取任务 ID
        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(
                Task.user_id == TEST_USER,
                Task.content == "待推迟任务"
            ).first()
            task_id = task.id

        # 推迟任务
        result = await defer_task(task_id, days=2, user_id=TEST_USER)

        assert result["success"] is True
        assert "已推迟" in result["content"]

        # 验证新截止日期
        with get_session(TEST_USER) as sess:
            task = sess.query(Task).filter(Task.id == task_id).first()
            expected_deadline = (date.today() + timedelta(days=2)).isoformat()
            assert task.deadline == expected_deadline


class TestDateNormalization:
    """日期归一化测试"""

    def test_normalize_today(self):
        """测试"今天""""
        from lingxi_qwenpaw.tools import _normalize_deadline

        result = _normalize_deadline("今天")
        assert result == date.today().isoformat()

    def test_normalize_tomorrow(self):
        """测试"明天""""
        from lingxi_qwenpaw.tools import _normalize_deadline

        result = _normalize_deadline("明天")
        expected = (date.today() + timedelta(days=1)).isoformat()
        assert result == expected

    def test_normalize_day_after_tomorrow(self):
        """测试"后天""""
        from lingxi_qwenpaw.tools import _normalize_deadline

        result = _normalize_deadline("后天")
        expected = (date.today() + timedelta(days=2)).isoformat()
        assert result == expected

    def test_normalize_iso_date(self):
        """测试 ISO 格式日期"""
        from lingxi_qwenpaw.tools import _normalize_deadline

        iso_date = "2025-12-31"
        result = _normalize_deadline(iso_date)
        assert result == iso_date

    def test_normalize_empty(self):
        """测试空字符串"""
        from lingxi_qwenpaw.tools import _normalize_deadline

        result = _normalize_deadline("")
        assert result == ""

        result = _normalize_deadline(None)
        assert result == ""

    def test_normalize_days_later(self):
        """测试"N天后" """
        from lingxi_qwenpaw.tools import _normalize_deadline

        result = _normalize_deadline("3天后")
        expected = (date.today() + timedelta(days=3)).isoformat()
        assert result == expected

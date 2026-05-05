"""桥接层测试

测试内容：
- get_emotion_engine
- get_life_engine
- 多租户实例管理
"""
import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

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

    # 清空桥接层缓存
    import lingxi_qwenpaw.bridge as bridge_module
    bridge_module._emotion_engines.clear()
    bridge_module._life_engines.clear()
    bridge_module._memory_layers.clear()
    bridge_module._pattern_engines.clear()
    bridge_module._agents.clear()
    bridge_module._memory_managers.clear()
    bridge_module._context_managers.clear()

    yield test_data_dir

    # 清理临时目录
    db_module.DATA_DIR = original_data_dir
    db_module.DB_DIR = original_db_dir
    db_module._engines.clear()
    db_module._SessionLocals.clear()
    bridge_module._emotion_engines.clear()
    bridge_module._life_engines.clear()
    bridge_module._memory_layers.clear()
    bridge_module._pattern_engines.clear()
    bridge_module._agents.clear()
    bridge_module._memory_managers.clear()
    bridge_module._context_managers.clear()
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestGetEmotionEngine:
    """get_emotion_engine 测试"""

    def test_get_emotion_engine_returns_instance(self, setup_test_environment):
        """测试返回情绪引擎实例"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        assert engine is not None
        assert hasattr(engine, "current_emotion")
        assert hasattr(engine, "emotion_intensity")

    def test_get_emotion_engine_same_user_same_instance(self, setup_test_environment):
        """测试同一用户返回相同实例"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine1 = get_emotion_engine(TEST_USER_1)
        engine2 = get_emotion_engine(TEST_USER_1)

        assert engine1 is engine2

    def test_get_emotion_engine_different_users_different_instances(self, setup_test_environment):
        """测试不同用户返回不同实例"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine1 = get_emotion_engine(TEST_USER_1)
        engine2 = get_emotion_engine(TEST_USER_2)

        assert engine1 is not engine2

    def test_emotion_engine_initial_state(self, setup_test_environment):
        """测试情绪引擎初始状态"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)
        state = engine.get_state()

        assert "emotion" in state
        assert "intensity" in state
        assert "emoji" in state
        assert "label" in state
        assert "is_grumpy" in state
        assert "is_shy" in state

    def test_emotion_engine_trigger(self, setup_test_environment):
        """测试情绪触发"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 触发开心情绪
        effect = engine.trigger("joy", 0.8, "测试触发")

        assert "mood_delta" in effect
        assert engine.current_emotion == "joy"
        assert engine.emotion_intensity == 0.8

    def test_emotion_engine_grumpy_state(self, setup_test_environment):
        """测试傲娇状态"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 触发傲娇情绪
        engine.trigger("anger", 0.7, "测试傲娇")

        state = engine.get_state()
        assert state["is_grumpy"] is True

    def test_emotion_engine_user_compliment(self, setup_test_environment):
        """测试用户夸奖"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        effect = engine.on_user_compliment()

        assert engine.is_shy is True
        assert "joy" in engine.current_emotion or engine.current_emotion == "joy"

    def test_emotion_engine_user_apologize(self, setup_test_environment):
        """测试用户道歉"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 先触发傲娇
        engine.trigger("anger", 0.7, "测试")
        assert engine.is_grumpy is True

        # 用户道歉
        effect = engine.on_user_apologize()

        assert engine.is_grumpy is False

    def test_emotion_engine_user_ignore(self, setup_test_environment):
        """测试用户忽略"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 多次忽略
        for _ in range(3):
            engine.on_user_ignore()

        # 应该触发傲娇
        state = engine.get_state()
        assert state["is_grumpy"] is True or engine.ignore_count >= 3


class TestGetLifeEngine:
    """get_life_engine 测试"""

    def test_get_life_engine_returns_instance(self, setup_test_environment):
        """测试返回生命引擎实例"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)

        assert engine is not None
        assert hasattr(engine, "state")
        assert hasattr(engine, "user_id")

    def test_get_life_engine_same_user_same_instance(self, setup_test_environment):
        """测试同一用户返回相同实例"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine1 = get_life_engine(TEST_USER_1)
        engine2 = get_life_engine(TEST_USER_1)

        assert engine1 is engine2

    def test_get_life_engine_different_users_different_instances(self, setup_test_environment):
        """测试不同用户返回不同实例"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine1 = get_life_engine(TEST_USER_1)
        engine2 = get_life_engine(TEST_USER_2)

        assert engine1 is not engine2

    def test_life_engine_initial_state(self, setup_test_environment):
        """测试生命引擎初始状态"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        state = engine.get_state()

        assert "energy" in state
        assert "mood" in state
        assert "curiosity" in state
        assert "social_need" in state
        assert "state" in state

    def test_life_engine_state_values_range(self, setup_test_environment):
        """测试生命状态值范围"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        state = engine.get_state()

        # 验证值范围
        assert 0 <= state["energy"] <= 100
        assert -5 <= state["mood"] <= 5
        assert 0 <= state["curiosity"] <= 100
        assert 0 <= state["social_need"] <= 100

    def test_life_engine_on_user_message(self, setup_test_environment):
        """测试用户消息处理"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        initial_mood = engine.state.mood
        initial_social = engine.state.social_need

        engine.on_user_message("你好")

        # 心情应该上升
        assert engine.state.mood >= initial_mood
        # 社交需求应该下降
        assert engine.state.social_need <= initial_social

    def test_life_engine_on_user_ignore(self, setup_test_environment):
        """测试用户忽略处理"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        initial_mood = engine.state.mood

        engine.on_user_ignore()

        # 心情应该下降
        assert engine.state.mood <= initial_mood
        assert engine.state.consecutive_ignored >= 1

    def test_life_engine_apply_emotion_effect(self, setup_test_environment):
        """测试应用情绪效果"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        initial_mood = engine.state.mood

        effect = {"mood_delta": 1.0, "energy_delta": 5.0, "social_need_delta": 0.0}
        engine.apply_emotion_effect(effect)

        assert engine.state.mood == initial_mood + 1.0

    def test_life_engine_get_behavior_prompt(self, setup_test_environment):
        """测试获取行为提示"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)
        prompt = engine.get_behavior_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_life_engine_get_proactive_message(self, setup_test_environment):
        """测试获取主动消息"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)

        # 初始应该没有主动消息
        msg = engine.get_proactive_message()
        assert msg is None

    def test_life_engine_user_id_set(self, setup_test_environment):
        """测试用户 ID 设置"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine = get_life_engine(TEST_USER_1)

        assert engine.user_id == TEST_USER_1


class TestGetMemoryLayer:
    """get_memory_layer 测试"""

    def test_get_memory_layer_returns_instance(self, setup_test_environment):
        """测试返回记忆层实例"""
        from lingxi_qwenpaw.bridge import get_memory_layer

        layer = get_memory_layer(TEST_USER_1)

        assert layer is not None

    def test_get_memory_layer_same_user_same_instance(self, setup_test_environment):
        """测试同一用户返回相同实例"""
        from lingxi_qwenpaw.bridge import get_memory_layer

        layer1 = get_memory_layer(TEST_USER_1)
        layer2 = get_memory_layer(TEST_USER_1)

        assert layer1 is layer2

    def test_get_memory_layer_different_users_different_instances(self, setup_test_environment):
        """测试不同用户返回不同实例"""
        from lingxi_qwenpaw.bridge import get_memory_layer

        layer1 = get_memory_layer(TEST_USER_1)
        layer2 = get_memory_layer(TEST_USER_2)

        assert layer1 is not layer2


class TestGetPatternEngine:
    """get_pattern_engine 测试"""

    def test_get_pattern_engine_returns_instance(self, setup_test_environment):
        """测试返回模式引擎实例"""
        from lingxi_qwenpaw.bridge import get_pattern_engine

        engine = get_pattern_engine(TEST_USER_1)

        assert engine is not None

    def test_get_pattern_engine_same_user_same_instance(self, setup_test_environment):
        """测试同一用户返回相同实例"""
        from lingxi_qwenpaw.bridge import get_pattern_engine

        engine1 = get_pattern_engine(TEST_USER_1)
        engine2 = get_pattern_engine(TEST_USER_1)

        assert engine1 is engine2

    def test_get_pattern_engine_different_users_different_instances(self, setup_test_environment):
        """测试不同用户返回不同实例"""
        from lingxi_qwenpaw.bridge import get_pattern_engine

        engine1 = get_pattern_engine(TEST_USER_1)
        engine2 = get_pattern_engine(TEST_USER_2)

        assert engine1 is not engine2


class TestMultiTenantIsolation:
    """多租户隔离测试"""

    def test_emotion_engine_isolation(self, setup_test_environment):
        """测试情绪引擎隔离"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine1 = get_emotion_engine(TEST_USER_1)
        engine2 = get_emotion_engine(TEST_USER_2)

        # 用户1触发情绪
        engine1.trigger("joy", 0.9, "测试")

        # 用户2不应该受影响
        assert engine2.current_emotion != "joy" or engine2.emotion_intensity != 0.9

    def test_life_engine_isolation(self, setup_test_environment):
        """测试生命引擎隔离"""
        from lingxi_qwenpaw.bridge import get_life_engine

        engine1 = get_life_engine(TEST_USER_1)
        engine2 = get_life_engine(TEST_USER_2)

        # 用户1处理消息
        engine1.on_user_message("你好")

        # 用户2不应该受影响
        assert engine2.state.ticks_without_user == 0

    def test_all_engines_per_user(self, setup_test_environment):
        """测试每个用户有独立的引擎集合"""
        from lingxi_qwenpaw.bridge import (
            get_emotion_engine,
            get_life_engine,
            get_memory_layer,
            get_pattern_engine,
        )

        # 获取两个用户的所有引擎
        emotion1 = get_emotion_engine(TEST_USER_1)
        emotion2 = get_emotion_engine(TEST_USER_2)

        life1 = get_life_engine(TEST_USER_1)
        life2 = get_life_engine(TEST_USER_2)

        memory1 = get_memory_layer(TEST_USER_1)
        memory2 = get_memory_layer(TEST_USER_2)

        pattern1 = get_pattern_engine(TEST_USER_1)
        pattern2 = get_pattern_engine(TEST_USER_2)

        # 验证所有引擎都是独立的
        assert emotion1 is not emotion2
        assert life1 is not life2
        assert memory1 is not memory2
        assert pattern1 is not pattern2


class TestEngineCaching:
    """引擎缓存测试"""

    def test_emotion_engine_caching(self, setup_test_environment):
        """测试情绪引擎缓存"""
        from lingxi_qwenpaw.bridge import get_emotion_engine, _emotion_engines

        # 清空缓存
        _emotion_engines.clear()

        # 第一次获取
        engine1 = get_emotion_engine(TEST_USER_1)
        assert TEST_USER_1 in _emotion_engines

        # 第二次获取应该返回缓存的实例
        engine2 = get_emotion_engine(TEST_USER_1)
        assert engine1 is engine2

    def test_life_engine_caching(self, setup_test_environment):
        """测试生命引擎缓存"""
        from lingxi_qwenpaw.bridge import get_life_engine, _life_engines

        # 清空缓存
        _life_engines.clear()

        # 第一次获取
        engine1 = get_life_engine(TEST_USER_1)
        assert TEST_USER_1 in _life_engines

        # 第二次获取应该返回缓存的实例
        engine2 = get_life_engine(TEST_USER_1)
        assert engine1 is engine2


class TestGetMemoryManager:
    """get_memory_manager 测试"""

    def test_get_memory_manager_returns_none_if_not_initialized(self, setup_test_environment):
        """测试未初始化时返回 None"""
        from lingxi_qwenpaw.bridge import get_memory_manager

        manager = get_memory_manager(TEST_USER_1)

        # 未初始化时应该返回 None
        assert manager is None


class TestGetContextManager:
    """get_context_manager 测试"""

    def test_get_context_manager_returns_none_if_not_initialized(self, setup_test_environment):
        """测试未初始化时返回 None"""
        from lingxi_qwenpaw.bridge import get_context_manager

        manager = get_context_manager(TEST_USER_1)

        # 未初始化时应该返回 None
        assert manager is None


class TestLLMCall:
    """LLM 调用测试"""

    @patch("lingxi_qwenpaw.bridge.httpx.Client")
    def test_llm_call_async_success(self, mock_client, setup_test_environment):
        """测试异步 LLM 调用成功"""
        from lingxi_qwenpaw.bridge import llm_call_async

        # 模拟响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试回复"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        result = llm_call_async("测试提示")

        assert result == "测试回复"

    @patch("lingxi_qwenpaw.bridge.httpx.Client")
    def test_llm_call_async_failure(self, mock_client, setup_test_environment):
        """测试异步 LLM 调用失败"""
        from lingxi_qwenpaw.bridge import llm_call_async

        # 模拟异常
        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = Exception("连接失败")
        mock_client.return_value.__enter__.return_value = mock_client_instance

        result = llm_call_async("测试提示")

        assert result == ""


class TestEmotionDecay:
    """情绪衰减测试"""

    def test_emotion_decay(self, setup_test_environment):
        """测试情绪衰减"""
        from lingxi_qwenpaw.bridge import get_emotion_engine
        import math

        engine = get_emotion_engine(TEST_USER_1)

        # 触发高强度情绪
        engine.trigger("joy", 0.9, "测试")

        # 获取衰减后的强度
        decayed = engine.get_decayed_intensity()

        # 衰减后的强度应该小于等于原始强度
        assert decayed <= 0.9

    def test_emotion_decay_returns_to_joy(self, setup_test_environment):
        """测试负面情绪衰减后回归开心"""
        from lingxi_qwenpaw.bridge import get_emotion_engine
        from datetime import datetime, timedelta

        engine = get_emotion_engine(TEST_USER_1)

        # 触发负面情绪
        engine.trigger("sadness", 0.9, "测试")

        # 模拟时间流逝（设置很久以前的触发时间）
        engine._last_trigger_time = datetime.utcnow() - timedelta(hours=10)

        # 获取衰减后的强度
        decayed = engine.get_decayed_intensity()

        # 强度应该很低
        assert decayed < 0.1

        # 情绪应该回归 joy
        assert engine.current_emotion == "joy"


class TestTrustSystem:
    """信任系统测试"""

    def test_trust_update(self, setup_test_environment):
        """测试信任更新"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)
        initial_trust = engine.trust_level

        # 增加信任
        engine.update_trust("compliment", 0.1)

        assert engine.trust_level == initial_trust + 0.1

    def test_trust_bounds(self, setup_test_environment):
        """测试信任边界"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 尝试超过上限
        engine.update_trust("test", 2.0)
        assert engine.trust_level <= 1.0

        # 尝试低于下限
        engine.update_trust("test", -2.0)
        assert engine.trust_level >= 0.0

    def test_trust_events_recorded(self, setup_test_environment):
        """测试信任事件记录"""
        from lingxi_qwenpaw.bridge import get_emotion_engine

        engine = get_emotion_engine(TEST_USER_1)

        # 记录信任事件
        engine.update_trust("compliment", 0.1)
        engine.update_trust("promise_broken", -0.2)

        assert len(engine.trust_events) == 2

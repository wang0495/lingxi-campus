"""灵犀 x qwenpaw 桥接层 — 多租户版本"""
import functools
import asyncio
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg, TextBlock

from lingxi_qwenpaw.logger import get_logger

logger = get_logger(__name__)

from lingxi_qwenpaw.config import LLM_API_URL, LLM_API_KEY, LLM_MODEL, EMBEDDING_API_KEY
from lingxi_qwenpaw.tools import TOOL_FUNCTIONS


# ─── 多租户 Memory & Context Managers ─────────────────────────────

_memory_managers: dict = {}
_context_managers: dict = {}


def get_memory_manager(user_id: str = "default"):
    return _memory_managers.get(user_id)


def get_context_manager(user_id: str = "default"):
    return _context_managers.get(user_id)


# ─── 多租户 Engine 实例 ──────────────────────────────────────────

_emotion_engines: dict = {}
_life_engines: dict = {}
_memory_layers: dict = {}
_pattern_engines: dict = {}


def get_emotion_engine(user_id: str = "default"):
    """获取指定用户的情绪引擎实例"""
    if user_id not in _emotion_engines:
        from lingxi_qwenpaw.plugins.emotion_engine import LingxiEmotionEngine
        _emotion_engines[user_id] = LingxiEmotionEngine()
    return _emotion_engines[user_id]


def get_life_engine(user_id: str = "default"):
    """获取指定用户的生命引擎实例"""
    if user_id not in _life_engines:
        from lingxi_qwenpaw.plugins.life_engine import LingxiLifeEngine, LifeState
        engine = object.__new__(LingxiLifeEngine)
        engine.user_id = user_id
        engine._initialized = False
        engine.state = LifeState()
        engine._last_daily_post_date = {}
        engine._last_nightly_post_date = {}
        engine._proactive_queue = []
        engine._tick_interval = 600
        engine._running = False
        engine._thread = None
        engine._last_user_time = 0.0
        engine._exploration_topics = {
            "share_life": [
                "刚才看到窗外的云好像棉花糖",
                "今天一直在想一个问题，为什么猫喜欢纸箱",
                "我发现了一个好玩的冷知识想分享给你",
                "刚才偷偷看了下你的日程，明天挺忙的",
                "今天校园里的花开了，好想出去看看",
            ],
            "care_user": [
                "你今天有没有好好吃饭呀",
                "记得喝水哦，别光顾着忙",
                "天气变凉了，注意加衣服",
                "最近是不是压力有点大",
            ],
            "random_thought": [
                "如果我能吃东西的话，最想吃火锅",
                "刚才在想，数字生命会不会做梦",
                "有时候觉得当个AI也不错，不用写作业",
                "你说我如果去参加辩论赛会不会很厉害",
            ],
        }
        _life_engines[user_id] = engine
    return _life_engines[user_id]


def get_memory_layer(user_id: str = "default"):
    """获取指定用户的记忆层实例"""
    if user_id not in _memory_layers:
        from lingxi_qwenpaw.plugins.memory_manager import MemoryLayer
        _memory_layers[user_id] = MemoryLayer(user_id=user_id)
    return _memory_layers[user_id]


def get_pattern_engine(user_id: str = "default"):
    """获取指定用户的行为模式引擎实例"""
    if user_id not in _pattern_engines:
        from lingxi_qwenpaw.plugins.pattern_engine import PatternEngine
        _pattern_engines[user_id] = PatternEngine(user_id=user_id)
    return _pattern_engines[user_id]


async def start_memory(user_id: str = "default"):
    """启动时初始化指定用户的 memory manager"""
    global _memory_managers, _context_managers

    # 初始化 workspace
    from lingxi_qwenpaw.workspace_init import init_workspace, get_workspace_dir
    init_workspace(user_id)
    working_dir = str(get_workspace_dir(user_id))

    # ReMeLightMemoryManager — 语义搜索 + dream + 自动摘要
    from qwenpaw.agents.memory.reme_light_memory_manager import ReMeLightMemoryManager
    _memory_managers[user_id] = ReMeLightMemoryManager(working_dir, "lingxi-campus")
    await _memory_managers[user_id].start()

    # LightContextManager — 上下文压缩 + 工具结果裁剪
    from qwenpaw.agents.context.light_context_manager import LightContextManager
    _context_managers[user_id] = LightContextManager(working_dir, "lingxi-campus")


async def close_memory(user_id: str = "default"):
    """关闭时清理指定用户资源"""
    if user_id in _memory_managers:
        await _memory_managers[user_id].close()
        del _memory_managers[user_id]
    if user_id in _context_managers:
        await _context_managers[user_id].close()
        del _context_managers[user_id]


# ─── 多租户 agent ──────────────────────────────────────────────────

_agents: dict[str, ReActAgent] = {}


def _wrap_tool(fn):
    """将灵犀工具（返回 dict）包装为返回 ToolResponse"""
    @functools.wraps(fn)
    async def wrapper(**kwargs):
        if asyncio.iscoroutinefunction(fn):
            result = await fn(**kwargs)
        else:
            result = fn(**kwargs)
        text = result.get("content", str(result)) if isinstance(result, dict) else str(result)
        return ToolResponse(content=[TextBlock(type="text", text=text)])
    return wrapper


def _load_chat_history(agent: ReActAgent, working_dir: str) -> None:
    """从 dialog_path 加载历史聊天记录到 agent memory"""
    try:
        from agentscope.message import Msg
        import json, os
        from pathlib import Path

        ctx = agent.memory
        if ctx is None:
            return

        dialog_path = Path(working_dir) / "dialog"
        if not dialog_path.exists():
            return
        jsonl_files = sorted(dialog_path.glob("*.jsonl"), key=lambda p: p.stem)
        if not jsonl_files:
            return

        loaded = 0
        for fp in jsonl_files:
            try:
                with open(fp, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg_dict = json.loads(line)
                            msg = Msg.from_dict(msg_dict)
                            ctx.content.append((msg, []))
                            loaded += 1
                        except Exception:
                            continue
            except Exception:
                continue

        if loaded > 0:
            logger.info(f"从 {len(jsonl_files)} 个文件加载了 {loaded} 条历史记录")
    except Exception as e:
        logger.error(f"加载聊天历史失败: {e}", exc_info=True)


def _setup_provider() -> None:
    """配置 DeepSeek provider（幂等）"""
    import json
    from pathlib import Path
    from qwenpaw.providers.provider_manager import ProviderManager
    from qwenpaw.constant import SECRET_DIR

    # 1. 确保 deepseek.json 存在且包含 API key
    builtin_dir = SECRET_DIR / "providers" / "builtin"
    builtin_dir.mkdir(parents=True, exist_ok=True)
    ds_path = builtin_dir / "deepseek.json"
    if ds_path.exists():
        with open(ds_path, "r", encoding="utf-8") as f:
            ds_cfg = json.load(f)
    else:
        ds_cfg = {
            "id": "deepseek", "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key": LLM_API_KEY,
            "chat_model": "OpenAIChatModel",
            "models": [
                {"id": "deepseek-chat", "name": "DeepSeek Chat"},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner"},
                {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash"},
                {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro"},
            ],
            "extra_models": [], "api_key_prefix": "sk-",
            "is_local": False, "freeze_url": True,
            "require_api_key": True, "is_custom": False,
            "support_model_discovery": False, "support_connection_check": True,
            "generate_kwargs": {}, "meta": {},
        }
    # 确保 api_key 正确（明文写入，qwenpaw 会自动加密）
    if not ds_cfg.get("api_key") or ds_cfg["api_key"].startswith("ENC:"):
        ds_cfg["api_key"] = LLM_API_KEY
    with open(ds_path, "w", encoding="utf-8") as f:
        json.dump(ds_cfg, f, indent=2, ensure_ascii=False)

    # 2. 确保 active_model.json 指向 deepseek
    active_path = SECRET_DIR / "providers" / "active_model.json"
    active_cfg = {"provider_id": "deepseek", "model": LLM_MODEL}
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump(active_cfg, f, indent=2)

    # 3. 重新加载 provider manager
    try:
        manager = ProviderManager.get_instance()
        manager.update_provider("deepseek", {"api_key": LLM_API_KEY})
        manager.load_active_model()
    except Exception:
        pass


def create_lingxi_agent(user_id: str = "default", max_iters: int = 5) -> ReActAgent:
    """创建灵犀 ReActAgent（挂载 ReMeLight + AgentContext）"""
    _setup_provider()
    from qwenpaw.agents.model_factory import create_model_and_formatter
    from lingxi_qwenpaw.workspace_init import get_workspace_dir
    model, formatter = create_model_and_formatter(agent_id="lingxi-campus")
    working_dir = str(get_workspace_dir(user_id))

    toolkit = Toolkit()
    # 注册自定义工具
    for name, func in TOOL_FUNCTIONS.items():
        toolkit.register_tool_function(_wrap_tool(func))

    # 注册 memory_search 工具
    mem_mgr = _memory_managers.get(user_id)
    if mem_mgr:
        for tool_fn in mem_mgr.list_memory_tools():
            toolkit.register_tool_function(tool_fn)

    # 用 AgentContext 替代默认 InMemoryMemory
    memory = None
    ctx_mgr = _context_managers.get(user_id)
    if ctx_mgr:
        memory = ctx_mgr.get_agent_context()

    agent = ReActAgent(
        name="lingxi",
        sys_prompt="你是灵犀，一个 AI 生活管家。",
        model=model,
        formatter=formatter,
        toolkit=toolkit,
        memory=memory,
        max_iters=max_iters,
    )

    # 加载历史聊天记录
    _load_chat_history(agent, working_dir)

    return agent


def get_bridge_agent(user_id: str = "default") -> ReActAgent:
    """获取或创建指定用户的 agent"""
    if user_id not in _agents:
        _agents[user_id] = create_lingxi_agent(user_id)
    return _agents[user_id]


def update_agent_sys_prompt(sys_prompt: str, user_id: str = "default"):
    """更新 agent 系统提示（每次对话前调用）"""
    agent = get_bridge_agent(user_id)
    agent._sys_prompt = sys_prompt


def add_assistant_message_to_memory(content: str, user_id: str = "default") -> None:
    """将灵犀的主动消息/回复加入 agent memory 并持久化"""
    try:
        agent = get_bridge_agent(user_id)
        mem = agent.memory
        if mem is None:
            return
        from agentscope.message import Msg
        import json
        from datetime import datetime
        from lingxi_qwenpaw.workspace_init import get_workspace_dir

        msg = Msg("assistant", content, "assistant")
        # 内存中
        mem.content.append((msg, []))

        # 持久化到对话文件
        try:
            dialog_path = get_workspace_dir(user_id) / "dialog"
            dialog_path.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            fp = dialog_path / f"{date_str}.jsonl"
            with open(fp, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"持久化消息失败: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"添加助手消息到记忆失败: {e}", exc_info=True)


async def agent_chat(user_message: str, user_id: str = "default") -> str:
    """单轮对话，返回文本回复"""
    user_msg = Msg("user", user_message, "user")
    agent = get_bridge_agent(user_id)
    reply = await agent.reply(user_msg)
    return reply.get_text_content() if reply else ""


# ─── 统一 LLM 调用（供 emotion_engine / life_engine 使用）─────────

_llm_model = None
_llm_formatter = None


def _get_llm_model_and_formatter():
    """延迟初始化 model + formatter"""
    global _llm_model, _llm_formatter
    if _llm_model is None:
        _setup_provider()
        from qwenpaw.agents.model_factory import create_model_and_formatter
        _llm_model, _llm_formatter = create_model_and_formatter()
    return _llm_model, _llm_formatter


def llm_call_async(prompt: str, temperature: float = 0.8) -> str:
    """异步调用 LLM（给同步环境用）"""
    import httpx

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{LLM_API_URL}/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM 调用失败: {e} | URL={LLM_API_URL}/chat/completions | model={LLM_MODEL}", exc_info=True)
        return ""


def llm_call(prompt: str, temperature: float = 0.8) -> str:
    """从同步环境调用 LLM（内部用 asyncio.run）"""
    return llm_call_async(prompt, temperature)


# ─── SiliconFlow 轻量模型（用于摘要等不需要强模型的场景）──────────────
import os
SF_LLM_URL = os.environ.get("SF_LLM_URL", "https://api.siliconflow.cn/v1/chat/completions")
SF_API_KEY = os.environ.get("SF_API_KEY", os.environ.get("EMBEDDING_API_KEY", ""))
SF_MODEL = os.environ.get("SF_MODEL", "Qwen/Qwen2.5-7B-Instruct")


def llm_call_sf(prompt: str, temperature: float = 0.7) -> str:
    """用 SiliconFlow 轻量模型调用 LLM（快、便宜）"""
    import httpx

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                SF_LLM_URL,
                json={
                    "model": SF_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {SF_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"SiliconFlow LLM 调用失败: {e}", exc_info=True)
        return ""

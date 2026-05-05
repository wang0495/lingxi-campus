"""
灵犀·校园 — Agent（简化版，不依赖 ~/.copaw/）

直接用 httpx 调用 DeepSeek LLM，不需要 QwenPaw 的 ProviderManager。
QwenPaw Agent 的 function calling 能力通过直接的工具调用实现。
"""
import asyncio
import inspect
from lingxi_qwenpaw.tools import TOOL_FUNCTIONS


def get_available_tools() -> dict:
    """返回所有可用工具（供 agent 选择调用）"""
    return TOOL_FUNCTIONS


async def call_tool(tool_name: str, **kwargs):
    """调用指定工具（支持 async/sync）"""
    if tool_name not in TOOL_FUNCTIONS:
        return {"success": False, "content": f"工具 {tool_name} 不存在"}
    func = TOOL_FUNCTIONS[tool_name]
    if inspect.iscoroutinefunction(func):
        return await func(**kwargs)
    return await asyncio.to_thread(func, **kwargs)

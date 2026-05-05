"""灵犀·校园 — workspace 初始化（多租户版本）

每个用户有独立的 workspace 目录：
  .qwenpaw_data/user_workspaces/{user_id}/
"""
import json
from pathlib import Path

from lingxi_qwenpaw.config import EMBEDDING_API_KEY

_LINGXI_DATA_DIR = Path(__file__).parent / ".qwenpaw_data"
_WORKSPACE_BASE = _LINGXI_DATA_DIR / "user_workspaces"


def get_workspace_dir(user_id: str = "default") -> Path:
    """返回指定用户的 workspace 目录路径"""
    return _WORKSPACE_BASE / user_id


def _get_config_path() -> Path:
    return _LINGXI_DATA_DIR / "config.json"


def init_workspace(user_id: str = "default") -> bool:
    """初始化用户 workspace，已存在则跳过。返回是否新建了文件。"""
    workspace_dir = get_workspace_dir(user_id)
    config_path = _get_config_path()

    # 已有配置则跳过（config.json 是全局的，只需初始化一次）
    if config_path.exists():
        return False

    _LINGXI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "memory").mkdir(exist_ok=True)
    (workspace_dir / "dialog").mkdir(exist_ok=True)

    # 1. config.json（根配置，告诉 qwenpaw agent 在哪）
    config_json = {
        "agents": {
            "active_agent": "lingxi-campus",
            "agent_order": ["lingxi-campus"],
            "profiles": {
                "lingxi-campus": {
                    "id": "lingxi-campus",
                    "workspace_dir": str(workspace_dir.resolve()),
                    "enabled": True,
                }
            }
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_json, f, ensure_ascii=False, indent=2)

    # 2. agent.json（agent 运行配置）
    agent_json = {
        "id": "lingxi-campus",
        "name": "灵犀·校园",
        "language": "zh",
        "workspace_dir": str(workspace_dir.resolve()),
        "active_model": {
            "provider_id": "deepseek",
            "model": "deepseek-v4-flash",
        },
        "approval_level": "AUTO",
        "system_prompt_files": ["SOUL.md"],
        "running": {
            "max_iters": 5,
            "max_input_length": 32768,
            "context_manager_backend": "light",
            "memory_manager_backend": "remelight",
            "reme_light_memory_config": {
                "summarize_when_compact": True,
                "auto_memory_interval": 10,
                "dream_cron": "0 23 * * *",
                "auto_memory_search_config": {
                    "enabled": True,
                    "max_results": 3,
                    "min_score": 0.3,
                },
                "embedding_model_config": {
                    "backend": "openai",
                    "api_key": EMBEDDING_API_KEY,
                    "base_url": "https://api.siliconflow.cn/v1",
                    "model_name": "BAAI/bge-m3",
                    "dimensions": 1024,
                    "enable_cache": True,
                },
            },
            "light_context_config": {
                "context_compact_config": {
                    "enabled": True,
                    "compact_threshold_ratio": 0.7,
                    "reserve_threshold_ratio": 0.15,
                },
                "tool_result_pruning_config": {
                    "enabled": True,
                    "pruning_recent_n": 2,
                    "pruning_old_msg_max_bytes": 3000,
                    "pruning_recent_msg_max_bytes": 50000,
                },
            },
        },
    }
    with open(workspace_dir / "agent.json", "w", encoding="utf-8") as f:
        json.dump(agent_json, f, ensure_ascii=False, indent=2)

    # 3. SOUL.md（从 soul.md 复制 + 追加记忆检索指引）
    soul_src = Path(__file__).parent / "soul.md"
    if soul_src.exists():
        soul_content = soul_src.read_text(encoding="utf-8")
    else:
        soul_content = "# 灵犀\n\n你是灵犀，一个 AI 生活管家。"

    soul_content += """

## 记忆检索

回答关于过往对话、用户偏好、历史决策的问题前，先调用 memory_search 检索相关记忆。
发现用户的新偏好、习惯、重要信息时，主动记录到 PROFILE.md 或 memory/每日笔记。
"""
    with open(workspace_dir / "SOUL.md", "w", encoding="utf-8") as f:
        f.write(soul_content)

    # 4. PROFILE.md（空模板）
    profile_md = """# 用户画像

## 基本信息
- 姓名：（待了解）
- 身份：大学生

## 偏好与习惯
（灵犀会在对话中自动补充）

## 近期关注
（灵犀会自动更新）
"""
    with open(workspace_dir / "PROFILE.md", "w", encoding="utf-8") as f:
        f.write(profile_md)

    # 5. MEMORY.md（空，dream 整理）
    with open(workspace_dir / "MEMORY.md", "w", encoding="utf-8") as f:
        f.write("# 长期记忆\n\n（dream 会自动整理有价值的内容到这里）\n")

    return True

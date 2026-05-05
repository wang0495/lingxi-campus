"""灵犀·校园 QwenPaw 灵魂后端 — 配置"""
import os
from pathlib import Path
from typing import Dict, List

# 项目根目录（比赛项目目录）
PROJECT_ROOT: Path = Path(__file__).parent.parent

# 数据库
DB_PATH: Path = PROJECT_ROOT / "lingxi.db"

# 加载 .env 文件（如果存在）
def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and value and key not in os.environ:
                        os.environ[key] = value

_load_env()

# LLM 配置
LLM_API_URL: str = os.environ.get("LLM_API_URL", "https://api.deepseek.com")
LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
LLM_MODEL: str = os.environ.get("LLM_MODEL", "deepseek-v4-flash")

# Embedding（用于记忆召回升级）
EMBEDDING_API_URL: str = os.environ.get("EMBEDDING_API_URL", "https://api.siliconflow.cn/v1/embeddings")
EMBEDDING_API_KEY: str = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")

# Vision (Qwen3-VL on SiliconFlow)
VISION_API_URL: str = os.environ.get("VISION_API_URL", "https://api.siliconflow.cn/v1/chat/completions")
VISION_API_KEY: str = os.environ.get("VISION_API_KEY", EMBEDDING_API_KEY)
VISION_MODEL: str = os.environ.get("VISION_MODEL", "Qwen/Qwen3-VL-8B-Instruct")

# STT (SenseVoice on SiliconFlow)
STT_API_URL: str = os.environ.get("STT_API_URL", "https://api.siliconflow.cn/v1/audio/transcriptions")
STT_API_KEY: str = os.environ.get("STT_API_KEY", EMBEDDING_API_KEY)
STT_MODEL: str = os.environ.get("STT_MODEL", "FunAudioLLM/SenseVoiceSmall")

# QwenPaw Agent 配置（保留结构，运行时由 bridge.py 管理）
AGENT_CONFIG: Dict[str, str] = {
    "id": "lingxi-campus",
    "name": "灵犀·校园",
    "description": "AI个人生活管家 — 像真人一样社交和生活的数字人",
    "language": "zh",
    "approval_level": "AUTO",
}

# ─── 业务分类常量 ───────────────────────────────────────────────

TIME_CATEGORIES: Dict[str, str] = {
    "tutoring": "上课/家教",
    "commute": "通勤",
    "prep": "备课",
    "homework": "作业",
    "thesis": "毕设",
    "content": "内容创作",
    "chore": "家务",
    "hygiene": "洗漱",
    "meal": "吃饭",
    "rest": "休息",
    "waste": "摸鱼",
    "other": "其他",
}

EXPENSE_CATEGORIES: List[str] = [
    "餐饮", "交通", "购物", "娱乐", "学习", "社交", "日用品", "医疗", "其他"
]

INCOME_SOURCES: List[str] = [
    "家教", "兼职", "奖学金", "生活费", "其他"
]

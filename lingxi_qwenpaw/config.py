"""灵犀·校园 QwenPaw 灵魂后端 — 配置"""
from pathlib import Path

# 项目根目录（比赛项目目录）
PROJECT_ROOT = Path(__file__).parent.parent

# 数据库
DB_PATH = PROJECT_ROOT / "lingxi.db"

# LLM 配置
LLM_API_URL = "https://api.deepseek.com"
LLM_API_KEY = "sk-8ba47cde059444619b5cede1095fcd7f"
LLM_MODEL = "deepseek-v4-flash"

# Embedding（用于记忆召回升级）
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_API_KEY = "sk-bkamiuygydnklotgniygaamxbnoostamrghxnjyvqwwfjhoo"
EMBEDDING_MODEL = "BAAI/bge-m3"

# Vision (Qwen3-VL on SiliconFlow)
VISION_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
VISION_API_KEY = EMBEDDING_API_KEY  # 同一个 SiliconFlow 账号
VISION_MODEL = "Qwen/Qwen3-VL-8B-Instruct"

# STT (SenseVoice on SiliconFlow)
STT_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
STT_API_KEY = EMBEDDING_API_KEY
STT_MODEL = "FunAudioLLM/SenseVoiceSmall"

# QwenPaw Agent 配置（保留结构，运行时由 bridge.py 管理）
AGENT_CONFIG = {
    "id": "lingxi-campus",
    "name": "灵犀·校园",
    "description": "AI个人生活管家 — 像真人一样社交和生活的数字人",
    "language": "zh",
    "approval_level": "AUTO",
}

# ─── 业务分类常量 ───────────────────────────────────────────────

TIME_CATEGORIES = {
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

EXPENSE_CATEGORIES = [
    "餐饮", "交通", "购物", "娱乐", "学习", "社交", "日用品", "医疗", "其他"
]

INCOME_SOURCES = [
    "家教", "兼职", "奖学金", "生活费", "其他"
]

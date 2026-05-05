"""灵犀·校园 — 独立 qwenpaw 配置初始化

在导入任何 qwenpaw 模块之前，设置 QWENPAW_SECRET_DIR 环境变量，
让灵犀使用项目本地的配置目录，不污染系统全局 qwenpaw 配置。
"""
import os
from pathlib import Path

# 项目本地数据目录（workspace、对话日志、记忆文件）
_LINGXI_WORKING_DIR = Path(__file__).parent / ".qwenpaw_data"
os.environ["QWENPAW_WORKING_DIR"] = str(_LINGXI_WORKING_DIR)

# 项目本地密钥目录（provider API key）
_LINGXI_SECRET_DIR = Path(__file__).parent / ".qwenpaw_secret"

# 必须在 import qwenpaw 之前设置，否则 qwenpaw.constant 会读取全局配置
os.environ["QWENPAW_SECRET_DIR"] = str(_LINGXI_SECRET_DIR)

# 确保目录存在
_LINGXI_WORKING_DIR.mkdir(parents=True, exist_ok=True)
_LINGXI_SECRET_DIR.mkdir(parents=True, exist_ok=True)

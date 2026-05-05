"""灵犀·校园 — JWT 用户认证"""
import json
import time
import hashlib
import secrets
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any

from lingxi_qwenpaw.logger import get_logger

logger = get_logger(__name__)

# 项目根目录
PROJECT_ROOT: Path = Path(__file__).parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
USERS_FILE: Path = DATA_DIR / "users.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# JWT 配置（从环境变量读取，生产环境必须设置强密钥）
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    # 开发环境生成临时密钥，生产环境必须设置环境变量
    JWT_SECRET = secrets.token_hex(32)
    logger.warning("JWT_SECRET 未设置，已生成临时密钥。生产环境请设置环境变量！")
JWT_ALGORITHM: str = "HS256"
TOKEN_EXPIRE_SECONDS: int = 30 * 60  # 30分钟（访问令牌有效期）
REFRESH_TOKEN_EXPIRE_SECONDS: int = 30 * 24 * 3600  # 30天（刷新令牌有效期）


def _load_users() -> Dict[str, Any]:
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: Dict[str, Any]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _hash_password(password: str, salt: str = "") -> str:
    """简单 PBKDF2 风格哈希"""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password + JWT_SECRET).encode()).hexdigest()
    return f"{salt}${h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        return _hash_password(password, salt) == stored
    except Exception:
        return False


def register(username: str, password: str) -> Dict[str, Any]:
    """注册用户。返回 {"ok": True} 或 {"ok": False, "error": "..."}"""
    username = username.strip()
    if len(username) < 2 or len(username) > 30:
        return {"ok": False, "error": "用户名需要2-30个字符"}
    
    # 密码强度验证
    if len(password) < 8:
        return {"ok": False, "error": "密码至少8个字符"}
    if len(password) > 128:
        return {"ok": False, "error": "密码不能超过128个字符"}
    if not re.search(r"[A-Za-z]", password):
        return {"ok": False, "error": "密码必须包含至少一个字母"}
    if not re.search(r"\d", password):
        return {"ok": False, "error": "密码必须包含至少一个数字"}

    users = _load_users()
    if username in users:
        return {"ok": False, "error": "用户名已存在"}

    users[username] = {
        "password_hash": _hash_password(password),
        "created_at": time.strftime("%Y-%m-%d"),
    }
    _save_users(users)
    return {"ok": True}


def login(username: str, password: str) -> Dict[str, Any]:
    """登录验证。返回 {"ok": True, "token": "...", "refresh_token": "..."} 或 {"ok": False, "error": "..."}"""
    users = _load_users()
    if username not in users:
        return {"ok": False, "error": "用户名或密码错误"}
    if not _verify_password(password, users[username]["password_hash"]):
        return {"ok": False, "error": "用户名或密码错误"}

    # 生成访问令牌（JWT，裸实现，不依赖 pyjwt）
    exp = int(time.time()) + TOKEN_EXPIRE_SECONDS
    payload = f"{username}.{exp}"
    sig = hashlib.sha256((payload + JWT_SECRET).encode()).hexdigest()[:32]
    token = f"{payload}.{sig}"

    # 生成刷新令牌（有效期 30 天）
    refresh_exp = int(time.time()) + REFRESH_TOKEN_EXPIRE_SECONDS
    refresh_payload = f"{username}.{refresh_exp}.refresh"
    refresh_sig = hashlib.sha256((refresh_payload + JWT_SECRET).encode()).hexdigest()[:32]
    refresh_token = f"{refresh_payload}.{refresh_sig}"

    return {"ok": True, "token": token, "refresh_token": refresh_token}


def verify_token(token: str) -> Optional[str]:
    """验证访问令牌（JWT），返回 user_id 或 None"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        username, exp_str, sig = parts
        exp = int(exp_str)
        if exp < int(time.time()):
            return None  # 过期
        payload = f"{username}.{exp_str}"
        expected_sig = hashlib.sha256((payload + JWT_SECRET).encode()).hexdigest()[:32]
        if sig != expected_sig:
            return None
        # 检查用户是否还存在
        if username not in _load_users():
            return None
        return username
    except Exception:
        return None


def verify_refresh_token(refresh_token: str) -> Optional[str]:
    """
    验证刷新令牌，返回 user_id 或 None
    
    刷新令牌格式：{username}.{exp}.refresh.{sig}
    """
    try:
        parts = refresh_token.split(".")
        if len(parts) != 4:
            return None
        username, exp_str, token_type, sig = parts
        # 验证令牌类型
        if token_type != "refresh":
            return None
        # 验证是否过期
        exp = int(exp_str)
        if exp < int(time.time()):
            return None  # 过期
        # 验证签名
        payload = f"{username}.{exp_str}.{token_type}"
        expected_sig = hashlib.sha256((payload + JWT_SECRET).encode()).hexdigest()[:32]
        if sig != expected_sig:
            return None
        # 检查用户是否还存在
        if username not in _load_users():
            return None
        return username
    except Exception:
        return None


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    使用刷新令牌生成新的访问令牌
    
    返回 {"ok": True, "token": "..."} 或 {"ok": False, "error": "..."}
    """
    username = verify_refresh_token(refresh_token)
    if not username:
        return {"ok": False, "error": "刷新令牌无效或已过期"}
    
    # 生成新的访问令牌
    exp = int(time.time()) + TOKEN_EXPIRE_SECONDS
    payload = f"{username}.{exp}"
    sig = hashlib.sha256((payload + JWT_SECRET).encode()).hexdigest()[:32]
    token = f"{payload}.{sig}"
    
    return {"ok": True, "token": token}

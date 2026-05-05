"""灵犀·校园 — JWT 用户认证"""
import json
import time
import hashlib
import secrets
from pathlib import Path
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# JWT 配置（demo 用，生产换复杂密钥）
JWT_SECRET = "lingxi-campus-secret-key-2024"
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 7 * 24 * 3600  # 7天


def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict):
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


def register(username: str, password: str) -> dict:
    """注册用户。返回 {"ok": True} 或 {"ok": False, "error": "..."}"""
    username = username.strip()
    if len(username) < 2 or len(username) > 30:
        return {"ok": False, "error": "用户名需要2-30个字符"}
    if len(password) < 4:
        return {"ok": False, "error": "密码至少4个字符"}

    users = _load_users()
    if username in users:
        return {"ok": False, "error": "用户名已存在"}

    users[username] = {
        "password_hash": _hash_password(password),
        "created_at": time.strftime("%Y-%m-%d"),
    }
    _save_users(users)
    return {"ok": True}


def login(username: str, password: str) -> dict:
    """登录验证。返回 {"ok": True, "token": "..."} 或 {"ok": False, "error": "..."}"""
    users = _load_users()
    if username not in users:
        return {"ok": False, "error": "用户名或密码错误"}
    if not _verify_password(password, users[username]["password_hash"]):
        return {"ok": False, "error": "用户名或密码错误"}

    # 生成 JWT（裸实现，不依赖 pyjwt）
    exp = int(time.time()) + TOKEN_EXPIRE_SECONDS
    payload = f"{username}.{exp}"
    sig = hashlib.sha256((payload + JWT_SECRET).encode()).hexdigest()[:32]
    token = f"{payload}.{sig}"
    return {"ok": True, "token": token}


def verify_token(token: str) -> Optional[str]:
    """验证 JWT，返回 user_id 或 None"""
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

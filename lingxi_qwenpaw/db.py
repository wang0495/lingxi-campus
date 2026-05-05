"""灵犀·校园 — 数据库层（多租户 SQLite）"""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
from contextvars import ContextVar
import json

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, Boolean,
    DateTime, JSON, ForeignKey, inspect, Index, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from lingxi_qwenpaw.exceptions import DatabaseError
from lingxi_qwenpaw.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 用户数据根目录
DATA_DIR = Path(__file__).parent.parent / "data"
DB_DIR = DATA_DIR / "user_data"

# ─── 用户上下文（用于在同步/异步调用链中传递 user_id）──────────────
_current_user_id: ContextVar[str] = ContextVar("current_user_id", default="default")


def set_current_user(user_id: str):
    """设置当前请求的用户上下文（必须在 get_session 调用前设置）"""
    _current_user_id.set(user_id)


def get_current_user_id() -> str:
    """获取当前上下文的 user_id"""
    return _current_user_id.get()


def get_db_path(user_id: str) -> Path:
    """返回指定用户的数据库路径"""
    return DB_DIR / user_id / "lingxi.db"


# ─── 多租户引擎缓存 ───────────────────────────────────────────────

_engines: dict[str, Any] = {}  # user_id → engine
_SessionLocals: dict[str, Any] = {}  # user_id → SessionLocal
Base = declarative_base()


def _add_missing_columns(engine):
    """为已有表补充新增列（ALTER TABLE）"""
    from sqlalchemy import text
    # (table, column, column_def)
    tables_cols = [
        ("tasks", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("time_logs", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("journal_entries", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("ledger_records", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("user_profiles", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("memory_entries", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("pattern_records", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("insights", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("social_posts", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("lingxi_life_events", "user_id", "VARCHAR(50) DEFAULT 'default'"),
        ("memory_entries", "recall_count", "INTEGER DEFAULT 0"),
        # 新增 updated_at 字段
        ("tasks", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ("journal_entries", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
        ("ledger_records", "updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
    ]
    with engine.connect() as conn:
        for table, col, col_def in tables_cols:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                conn.commit()
            except Exception as e:
                # 列已存在是正常情况，记录调试日志即可
                logger.debug(f"添加列 {table}.{col} 失败（可能已存在）: {e}")


def _get_engine_and_session(user_id: str):
    """获取或创建指定用户的 engine + SessionLocal"""
    if user_id not in _engines:
        db_path = get_db_path(user_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        # 补充新列（已有数据库需要 ALTER TABLE）
        _add_missing_columns(engine)
        _engines[user_id] = engine
        _SessionLocals[user_id] = SessionLocal
    return _engines[user_id], _SessionLocals[user_id]


def get_session(user_id: Optional[str] = None) -> Session:
    """获取指定用户的数据库会话。user_id 为 None 时使用上下文中的当前用户"""
    if user_id is None:
        user_id = _current_user_id.get()
    _, SessionLocal = _get_engine_and_session(user_id)
    return SessionLocal()


# ─── 模型（保持不变） ─────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_deadline", "user_id", "deadline"),
        CheckConstraint('urgency >= 1 AND urgency <= 5', name='check_urgency_range'),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    item_type = Column(String(20), default="task")
    content = Column(Text)
    from_source = Column(String(100), nullable=True)
    urgency = Column(Integer, default=3)
    deadline = Column(String(20), nullable=True)
    effort = Column(String(10), nullable=True)
    tags = Column(JSON, default=list)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    done_at = Column(DateTime, nullable=True)
    deferred_to = Column(String(20), nullable=True)
    waiting_for = Column(String(100), nullable=True)


class TimeLog(Base):
    __tablename__ = "time_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    category = Column(String(50))
    minutes = Column(Integer)
    note = Column(Text, nullable=True)
    date = Column(String(20))  # YYYY-MM-DD
    created_at = Column(DateTime, default=datetime.utcnow)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    date = Column(String(20))  # YYYY-MM-DD
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LedgerRecord(Base):
    __tablename__ = "ledger_records"
    __table_args__ = (
        Index("ix_ledger_user_date", "user_id", "date"),
        CheckConstraint('amount >= 0', name='check_amount_non_negative'),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    record_type = Column(String(10))  # income / expense
    amount = Column(Float)
    category = Column(String(50))
    note = Column(Text, nullable=True)
    date = Column(String(20))  # YYYY-MM-DD
    budget_month = Column(String(7), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    learning_style = Column(String(20), default="unknown")
    active_hours = Column(JSON, default=list)
    stress_level = Column(Integer, default=5)
    current_goals = Column(JSON, default=list)
    known_patterns = Column(JSON, default=list)
    preferred_tone = Column(String(20), default="friendly")
    sleep_time = Column(String(5), default="23:00")
    wake_time = Column(String(5), default="07:00")
    social_preference = Column(String(10), default="")
    last_update_reason = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    __table_args__ = (
        Index("ix_memory_user_layer", "user_id", "layer"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    layer = Column(String(20))  # observation / experience / pattern / model
    content = Column(Text)
    source_event = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.5)
    importance = Column(Integer, default=5)  # 1-10
    related_entities = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    shown_to_user = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    consolidation_level = Column(Integer, default=0)
    consolidated_from = Column(JSON, nullable=True)
    consolidated_into = Column(Integer, nullable=True)
    consolidated_at = Column(DateTime, nullable=True)
    recall_count = Column(Integer, default=0)  # 被召回次数，用于艾宾浩斯增强


class PatternRecord(Base):
    __tablename__ = "pattern_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    pattern_type = Column(String(50))
    description = Column(Text)
    lifecycle_stage = Column(String(20), default="discovered")
    first_seen = Column(String(20), nullable=True)
    last_seen = Column(String(20), nullable=True)
    occurrence_count = Column(Integer, default=0)
    intervention_attempts = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    evidence = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")
    insight_type = Column(String(30))
    title = Column(String(200), default="")
    content = Column(Text)
    severity = Column(Integer, default=3)  # 1-5
    related_tasks = Column(JSON, default=list)
    related_patterns = Column(JSON, default=list)
    is_read = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SocialPost(Base):
    __tablename__ = "social_posts"
    id = Column(Integer, primary_key=True)
    author_id = Column(String(50), default="lingxi")
    author_name = Column(String(50), default="灵犀")
    user_id = Column(String(50), default="default")  # 多租户：属于哪个用户
    content = Column(Text)
    post_type = Column(String(20))
    mood_at_post = Column(Float, nullable=True)
    energy_at_post = Column(Float, nullable=True)
    related_data = Column(JSON, nullable=True)
    likes = Column(Integer, default=0)
    comments = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class LingxiLifeEvent(Base):
    __tablename__ = "lingxi_life_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), default="default")  # 多租户：属于哪个用户
    event_type = Column(String(20))
    summary = Column(Text)
    mood = Column(Float)
    energy = Column(Float)
    emotion = Column(String(20))
    story_arc = Column(String(30))
    importance = Column(Integer, default=5)
    related_post_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── 兼容性别名（启动时初始化默认用户） ───────────────────────────

def init_db():
    """确保默认用户数据库表存在（向后兼容）"""
    _get_engine_and_session("default")


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "item_type": task.item_type,
        "content": task.content,
        "urgency": task.urgency,
        "status": task.status,
        "deadline": task.deadline,
        "effort": task.effort,
        "tags": task.tags or [],
        "waiting_for": task.waiting_for,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "done_at": task.done_at.isoformat() if task.done_at else None,
    }


# 启动时初始化默认用户（兼容旧代码）
init_db()

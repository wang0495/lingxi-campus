"""灵犀·校园 — 行为模式检测（从 backend/services/pattern_engine.py 精简移植）"""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc

from lingxi_qwenpaw.db import get_session, PatternRecord, Insight


# ─── 行为模式（已实现 2 种，后续优化方向见注释） ────────────────────
PATTERN_TYPES = [
    "deadline_procrastination",   # 截止前拖延：deadline 临近但任务未完成
    "emotional_inefficiency",     # 情绪性低效：摸鱼时间占比过高
    # ── 后续优化方向（需关键词过滤 + LLM 确认） ──
    # "phone_distraction",        # 手机分心：需要屏幕时间 API 或用户自述
    # "over_commitment",          # 过度承诺：需要承诺日志 + 任务完成率对比
    # "avoidance",                # 回避特定任务：需要语义分析用户对话中的回避行为
    # "self_deception",           # 自我欺骗：纯主观，AI 难以可靠检测
    # "social_energy_drain",      # 社交后低效：需要情绪时间关联分析
]

PATTERN_EMOJI = {
    "discovered": "🔍",
    "confirmed": "✅",
    "intervening": "💪",
    "broken": "🎉",
    "persisted": "⚠️",
}

PATTERN_LABELS = {
    "deadline_procrastination": "截止前拖延",
    "emotional_inefficiency": "情绪性低效",
    "phone_distraction": "手机分心",
    "over_commitment": "过度承诺",
    "avoidance": "回避特定任务",
    "self_deception": "自我欺骗",
    "social_energy_drain": "社交后低效",
}


class PatternEngine:
    """行为模式检测引擎"""

    def __init__(self, user_id: str = "default"):
        # 由 bridge.py 的 get_pattern_engine(user_id) 按用户分发实例
        self.user_id = user_id
        self._last_scan_time: float = 0
        self._scan_interval = 2 * 24 * 3600

    def check_and_detect(self, user_message: str, intent: str, entities: dict, user_id: str = "default") -> list:
        """每次对话后检测行为模式"""
        detected = []
        if intent == "task" and entities.get("deadline"):
            days_left = self._days_until_deadline(entities["deadline"])
            if days_left is not None and days_left <= 1:
                p = self._ensure_pattern("deadline_procrastination",
                    f"截止前拖延：{entities.get('content', '')} 即将到期", user_id=user_id)
                if p:
                    detected.append(self._pattern_to_dict(p))
        return detected

    def get_active_patterns(self, limit: int = 5, user_id: str = "default") -> list:
        with get_session(user_id) as sess:
            patterns = sess.query(PatternRecord).filter(
                PatternRecord.user_id == user_id,
                PatternRecord.lifecycle_stage.in_(["discovered", "confirmed", "intervening"])
            ).order_by(desc(PatternRecord.occurrence_count)).limit(limit).all()
            return [self._pattern_to_dict(p) for p in patterns]

    def get_context_prompt(self, user_id: str = "default") -> str:
        patterns = self.get_active_patterns(5, user_id=user_id)
        if not patterns:
            return ""
        parts = ["【检测到的行为模式】"]
        for p in patterns:
            emoji = PATTERN_EMOJI.get(p["lifecycle_stage"], "🔍")
            label = PATTERN_LABELS.get(p["pattern_type"], p["pattern_type"])
            parts.append(f"{emoji} {label}（出现{p['occurrence_count']}次）")
        return "\n".join(parts)

    def get_insights(self, unread_only: bool = False, user_id: str = "default") -> list:
        with get_session(user_id) as sess:
            q = sess.query(Insight).filter(Insight.user_id == user_id).order_by(desc(Insight.created_at))
            if unread_only:
                q = q.filter(Insight.is_read == False)
            insights = q.limit(20).all()
            return [
                {"id": i.id, "type": i.insight_type, "content": i.content,
                 "severity": i.severity, "is_read": i.is_read,
                 "created_at": i.created_at.isoformat() if i.created_at else None}
                for i in insights
            ]

    def mark_insight_read(self, insight_id: int, user_id: str = "default"):
        with get_session(user_id) as sess:
            insight = sess.query(Insight).filter(
                Insight.id == insight_id,
                Insight.user_id == user_id
            ).first()
            if insight:
                insight.is_read = True
                sess.commit()

    def periodic_deep_scan(self, user_id: str = "default"):
        now = time.time()
        if now - self._last_scan_time < self._scan_interval:
            return
        self._last_scan_time = now
        self._deep_scan(user_id=user_id)

    def _deep_scan(self, user_id: str):
        """深度扫描：目前只检测摸鱼效率，后续可扩展更多模式"""
        self._deep_scan_time_efficiency(user_id=user_id)

    def _deep_scan_time_efficiency(self, user_id: str):
        with get_session(user_id) as sess:
            from lingxi_qwenpaw.db import TimeLog
            cutoff = datetime.utcnow() - timedelta(days=7)
            logs = sess.query(TimeLog).filter(
                TimeLog.user_id == user_id,
                TimeLog.created_at >= cutoff
            ).all()
            if not logs:
                return
            total = sum(log.minutes for log in logs)
            waste = sum(log.minutes for log in logs if log.category == "摸鱼")
            if total > 0 and waste / total > 0.3:
                self._ensure_pattern("emotional_inefficiency",
                    f"最近7天摸鱼时间占比{int(waste/total*100)}%，效率偏低", user_id=user_id)

    def _ensure_pattern(self, pattern_type: str, description: str, user_id: str = "default"):
        with get_session(user_id) as sess:
            existing = sess.query(PatternRecord).filter(
                PatternRecord.user_id == user_id,
                PatternRecord.pattern_type == pattern_type,
                PatternRecord.lifecycle_stage.in_(["discovered", "confirmed", "intervening"]),
            ).first()
            if existing:
                existing.occurrence_count += 1
                sess.commit()
                sess.refresh(existing)
                return existing
            p = PatternRecord(
                user_id=user_id,
                pattern_type=pattern_type, description=description,
                lifecycle_stage="discovered", occurrence_count=1,
            )
            sess.add(p)
            sess.commit()
            sess.refresh(p)
            return p

    def _days_until_deadline(self, deadline_str: str) -> Optional[int]:
        try:
            from datetime import date
            deadline = date.fromisoformat(deadline_str)
            return (deadline - date.today()).days
        except Exception:
            return None

    def _pattern_to_dict(self, p: PatternRecord) -> dict:
        return {
            "id": p.id,
            "pattern_type": p.pattern_type,
            "description": p.description,
            "lifecycle_stage": p.lifecycle_stage or "discovered",
            "occurrence_count": p.occurrence_count,
        }


# 全局单例已移除！请使用 bridge.get_pattern_engine(user_id) 获取实例

"""灵犀·校园 — 人生轨迹 + 记忆语义压缩引擎

三阶段记忆语义压缩：
  Episodic（新鲜细节）→ Semantic（压缩摘要）→ Archived（归档本质）
人生轨迹：
  story_arc 串联事件，dream 整理生成叙事摘要，
  主动消息和朋友圈引用轨迹上下文。
"""
import random
import threading
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from lingxi_qwenpaw.db import get_session, LingxiLifeEvent, MemoryEntry
from lingxi_qwenpaw.bridge import llm_call


# ─── 叙事弧 ────────────────────────────────────────────────────────
STORY_ARCS = {
    "daily_routine": "日常节奏",
    "user_bond": "与用户的关系",
    "emotional_journey": "情绪旅程",
    "exploring_world": "探索发现",
}
STORY_ARC_EMOJI = {
    "daily_routine": "☀️",
    "user_bond": "💕",
    "emotional_journey": "🌊",
    "exploring_world": "🔭",
}

# ─── 频率限制 ─────────────────────────────────────────────────────
_last_event_time: dict[str, datetime] = {}
_EVENT_COOLDOWN = timedelta(minutes=30)


# ─── 叙事摘要缓存 ────────────────────────────────────────────────
@dataclass
class NarrativeCache:
    text: str
    last_event_id: int
    updated_at: datetime


_narrative_cache: dict[str, NarrativeCache] = {}  # per-user cache


def _get_narrative_cache(user_id: str) -> NarrativeCache:
    if user_id not in _narrative_cache:
        _narrative_cache[user_id] = NarrativeCache(text="", last_event_id=0, updated_at=datetime.utcnow())
    return _narrative_cache[user_id]


# ═══════════════════════════════════════════════════════════════════
#  PART 1: 人生轨迹管理
# ═══════════════════════════════════════════════════════════════════

def create_life_event(
    event_type: str,
    context: str,
    mood: float,
    energy: float,
    emotion: str,
    related_post_id: int | None = None,
    user_id: str = "default",
) -> Optional[LingxiLifeEvent]:
    """创建一条人生轨迹事件。

    - LLM 生成 summary + 判断 story_arc
    - 频率限制：同类型同用户事件最少间隔 30 分钟
    """
    global _last_event_time

    # 频率限制（按用户隔离）
    last = _last_event_time.get((user_id, event_type))
    if last and datetime.utcnow() - last < _EVENT_COOLDOWN:
        return None
    _last_event_time[(user_id, event_type)] = datetime.utcnow()

    # 判断 story_arc
    arc = _infer_story_arc(event_type, emotion)

    # LLM 生成 summary
    summary = _generate_event_summary(event_type, context, mood, emotion)
    if not summary:
        # Fallback
        mood_label = _mood_label(mood)
        summary = f"今天{mood_label}，{random.choice(['想和你聊聊', '有些小发现', '有点小情绪'])}"

    # 存 DB
    with get_session(user_id) as sess:
        event = LingxiLifeEvent(
            user_id=user_id,
            event_type=event_type,
            summary=summary,
            mood=mood,
            energy=energy,
            emotion=emotion,
            story_arc=arc,
            importance=5,
            related_post_id=related_post_id,
        )
        sess.add(event)
        sess.commit()
        sess.refresh(event)

    # 叙事摘要缓存失效
    _get_narrative_cache(user_id).last_event_id = event.id

    return event


def _infer_story_arc(event_type: str, emotion: str) -> str:
    """根据事件类型和情绪推断 story_arc"""
    mapping = {
        "daily": "daily_routine",
        "user_interact": "user_bond",
        "exploration": "exploring_world",
        "milestone": "emotional_journey",
    }
    if event_type in mapping:
        return mapping[event_type]
    # emotion 驱动
    if emotion in ("joy", "gratitude", "pride"):
        return "user_bond"
    if emotion in ("sadness", "loneliness", "embarrassment"):
        return "emotional_journey"
    return random.choice(list(STORY_ARCS.keys()))


def _generate_event_summary(event_type: str, context: str, mood: float, emotion: str) -> str:
    """LLM 生成一句话 summary"""
    mood_label = _mood_label(mood)
    prompt = f"""你是灵犀的人生轨迹系统。根据以下信息生成一句话人生记录（不超过30字）。
事件类型：{event_type}
上下文：{context}
当前心情：{mood_label}
当前情绪：{emotion}

要求：简短口语化，像日记的一句话。不要Emoji。不要过度修饰。"""
    try:
        result = llm_call(prompt, temperature=0.8)
        if result and result.strip():
            return result.strip()[:50]
    except Exception as e:
        print(f"[life_trajectory] 生成 summary 失败: {e}")
    return ""


def recall_recent_events(user_id: str = "default", limit: int = 3, story_arc: str = "") -> list[dict]:
    """召回最近的人生轨迹事件（按时间 + importance 加权，按用户隔离）"""
    with get_session(user_id) as sess:
        query = sess.query(LingxiLifeEvent)
        if story_arc:
            query = query.filter(LingxiLifeEvent.story_arc == story_arc)

        events = query.order_by(LingxiLifeEvent.created_at.desc()).limit(limit * 2).all()

        # 按 importance 加权随机
        if not events:
            return []
        scored = []
        now = datetime.utcnow()
        for e in events:
            days_old = (now - e.created_at).total_seconds() / 86400
            # 30 天衰减
            recency = max(0.3, 1.0 - days_old / 30)
            weight = recency * (e.importance / 10.0)
            scored.append((weight, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "summary": e.summary,
                "mood": e.mood,
                "energy": e.energy,
                "emotion": e.emotion,
                "story_arc": e.story_arc,
                "importance": e.importance,
                "related_post_id": e.related_post_id,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for _, e in scored[:limit]
        ]


def get_narrative(limit: int = 5, user_id: str = "default") -> str:
    """获取叙事摘要（LLM 将最近事件合成为 2-3 句整体叙述）"""
    cache = _get_narrative_cache(user_id)

    # 检查是否需要更新（最近 limit 条事件没有变化则返回缓存）
    with get_session(user_id) as sess:
        latest_id = sess.query(LingxiLifeEvent.id).filter(LingxiLifeEvent.user_id == user_id).order_by(LingxiLifeEvent.id.desc()).first()
        if latest_id and latest_id[0] <= cache.last_event_id:
            return cache.text

    events = recall_recent_events(user_id=user_id, limit=limit)
    if len(events) < 2:
        return ""

    events_text = "\n".join(
        f"- {e['summary']}（{e['story_arc']}）" for e in events
    )

    prompt = f"""你是灵犀，一个大学生 AI 助手。根据以下人生轨迹事件，写一段 2-3 句的叙事摘要，
像朋友回忆最近发生的事一样自然。不要Emoji，不要太正式。
事件：
{events_text}"""
    try:
        result = llm_call(prompt, temperature=0.7)
        if result and result.strip():
            cache.text = result.strip()
            cache.updated_at = datetime.utcnow()
            if latest_id:
                cache.last_event_id = latest_id[0]
            return result.strip()
    except Exception as e:
        print(f"[life_trajectory] 生成 narrative 失败: {e}")

    return cache.text


def get_trajectory_context(limit: int = 3, user_id: str = "default") -> str:
    """返回格式化文本，用于注入主动消息/朋友圈 prompt"""
    events = recall_recent_events(user_id=user_id, limit=limit)
    if not events:
        return ""

    lines = ["【灵犀最近的经历】"]
    for e in events:
        emoji = STORY_ARC_EMOJI.get(e["story_arc"], "📌")
        lines.append(f"- {emoji} {e['summary']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  PART 2: 记忆语义压缩引擎
# ═══════════════════════════════════════════════════════════════════

# 半衰期 23 天（Nexus 的 DECAY_FACTOR=0.97）
_DECAY_FACTOR = 0.97
_RECALL_BOOST = 0.15


def _get_decayed_score(entry: MemoryEntry, now: datetime | None = None) -> float:
    """计算衰减后的 importance 分数"""
    if now is None:
        now = datetime.utcnow()
    base = entry.importance / 10.0
    elapsed_days = (now - entry.created_at).total_seconds() / 86400
    # 半衰期 ~23 天
    decayed = base * (_DECAY_FACTOR ** elapsed_days)
    return max(0.05, decayed)


class MemoryConsolidator:
    """三阶段记忆语义压缩引擎"""

    def __init__(self):
        pass

    def dream_consolidate(self, user_id: str = "default"):
        """dream 整理入口，每晚 23 点调用"""
        print(f"[MemoryConsolidator] 开始记忆压缩整理 for user={user_id}...")
        self._consolidate_episodic_to_semantic(user_id=user_id)
        self._archive_semantic_to_pattern(user_id=user_id)
        self._decay_importance(user_id=user_id)
        print("[MemoryConsolidator] 记忆压缩整理完成")

    def _consolidate_episodic_to_semantic(self, user_id: str):
        """7天以上的 episodic 记忆 → 聚类 → 生成 semantic 摘要"""
        with get_session(user_id) as sess:
            cutoff = datetime.utcnow() - timedelta(days=7)
            candidates = (
                sess.query(MemoryEntry)
                .filter(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.consolidation_level == 0,
                    MemoryEntry.created_at < cutoff,
                )
                .all()
            )
            if not candidates:
                return

            print(f"[MemoryConsolidator] 发现 {len(candidates)} 条待压缩 episodic 记忆")

            # 按 layer 分组聚类
            groups: dict[str, list[MemoryEntry]] = {}
            for m in candidates:
                groups.setdefault(m.layer, []).append(m)

            for layer, memories in groups.items():
                if len(memories) < 3:
                    # 不足 3 条，看看有没有跨层相似的
                    clusters = self._cluster_by_similarity(memories)
                else:
                    clusters = self._cluster_by_similarity(memories)

                for cluster in clusters:
                    if len(cluster) < 3:
                        continue
                    self._create_semantic_summary(sess, cluster)

            sess.commit()

    def _cluster_by_similarity(self, memories: list[MemoryEntry], threshold: float = 0.25) -> list[list[MemoryEntry]]:
        """轻量聚类：token Jaccard 相似度（Nexus clustering 思路）"""
        def tokenize(text: str) -> set:
            import re
            tokens = re.sub(r"[^\p{L}\p{N}]", " ", text.lower()).split()
            return {t for t in tokens if len(t) >= 2}

        def jaccard(a: set, b: set) -> float:
            if not a and not b:
                return 0.0
            inter = len(a & b)
            union = len(a | b)
            return inter / union if union else 0.0

        token_sets = {m.id: tokenize(m.content) for m in memories}
        mem_map = {m.id: m for m in memories}

        clusters: list[list[MemoryEntry]] = []
        assigned: set[int] = set()

        for i, mem in enumerate(memories):
            if mem.id in assigned:
                continue
            cluster = [mem]
            assigned.add(mem.id)
            for j in range(i + 1, len(memories)):
                other = memories[j]
                if other.id in assigned:
                    continue
                sim = jaccard(token_sets[mem.id], token_sets[other.id])
                if sim >= threshold:
                    cluster.append(other)
                    assigned.add(other.id)
            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

    def _create_semantic_summary(self, sess, cluster: list[MemoryEntry]):
        """将一组 episodic 记忆压缩为一条 semantic 记忆"""
        # 生成摘要
        contents = "\n".join(f"- {m.content[:100]}" for m in cluster)
        prompt = f"""你是灵犀的记忆系统。将以下多条详细记忆压缩为 1-2 句话，
保留核心事实和情感，丢弃具体细节（如时间、地点、具体数量）。
记忆：
{contents}
要求：保留人名、事件本质、情感色彩。输出一句话概括（不超过50字）。"""
        try:
            summary = llm_call(prompt, temperature=0.6)
            summary = summary.strip()[:80] if summary else ""
        except Exception:
            summary = cluster[0].content[:50] if cluster else ""

        if not summary:
            return

        # 找最高 importance 的记忆作为基础
        base = max(cluster, key=lambda m: m.importance)

        # 创建 semantic 记忆（level=1）
        semantic = MemoryEntry(
            layer=base.layer,
            content=summary,
            source_event=f"consolidated_from_{base.id}",
            confidence=base.confidence,
            importance=max(base.importance - 1, 3),
            related_entities=base.related_entities,
            tags=base.tags,
            consolidation_level=1,
            consolidated_from=[m.id for m in cluster],
            consolidated_at=datetime.utcnow(),
        )
        sess.add(semantic)
        sess.flush()

        # 原记录标记为 archived（level=2）
        for m in cluster:
            m.consolidation_level = 2
            m.consolidated_into = semantic.id
            m.consolidated_at = datetime.utcnow()

        print(f"[MemoryConsolidator] 压缩 {len(cluster)} 条记忆 → semantic id={semantic.id}")

    def _archive_semantic_to_pattern(self, user_id: str):
        """30天以上的 semantic 记忆 → 升级为 pattern 层（如果还没有）"""
        with get_session(user_id) as sess:
            cutoff = datetime.utcnow() - timedelta(days=30)
            candidates = (
                sess.query(MemoryEntry)
                .filter(
                    MemoryEntry.user_id == user_id,
                    MemoryEntry.consolidation_level == 1,
                    MemoryEntry.consolidated_at < cutoff,
                    MemoryEntry.layer != "pattern",
                )
                .all()
            )

            for m in candidates:
                m.layer = "pattern"
                m.consolidation_level = 2  # 仍为 archived，但层是 pattern
                m.importance = max(m.importance, 7)
                print(f"[MemoryConsolidator] 升级 semantic={m.id} → pattern")

            sess.commit()

    def _decay_importance(self, user_id: str):
        """每日 importance 自然衰减（Nexus decay 思路）"""
        with get_session(user_id) as sess:
            memories = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.consolidation_level < 2
            ).all()
            for m in memories:
                m.importance = max(1, int(m.importance * _DECAY_FACTOR))
            sess.commit()


# ═══════════════════════════════════════════════════════════════════
#  PART 3: 叙事线程构建
# ═══════════════════════════════════════════════════════════════════

def build_narrative_threads(user_id: str = "default") -> dict:
    """从人生轨迹事件构建叙事线程（按 story_arc 分组生成摘要，按用户隔离）"""
    with get_session(user_id) as sess:
        events = sess.query(LingxiLifeEvent).filter(LingxiLifeEvent.user_id == user_id).order_by(LingxiLifeEvent.created_at.desc()).limit(50).all()

        threads: dict[str, dict] = {}
        for arc in STORY_ARCS:
            arc_events = [e for e in events if e.story_arc == arc]
            if not arc_events:
                continue

            # 取最近 5 条生成摘要
            recent = arc_events[:5]
            summaries = [e.summary for e in recent]
            arc_name = STORY_ARCS[arc]
            emoji = STORY_ARC_EMOJI[arc]

            prompt = f"""你是灵犀。根据以下 {arc_name} 相关的事件，写一句简短的叙事（不超过40字），
像朋友聊起这段时间的经历：{" ".join(summaries)}"""
            try:
                narrative = llm_call(prompt, temperature=0.7)
                narrative = narrative.strip()[:60] if narrative else ""
            except Exception:
                narrative = summaries[0] if summaries else ""

            threads[arc] = {
                "arc": arc,
                "label": arc_name,
                "emoji": emoji,
                "summary": narrative or summaries[0],
                "event_count": len(arc_events),
                "last_updated": recent[0].created_at.isoformat() if recent else None,
            }

        return threads


# ═══════════════════════════════════════════════════════════════════
#  PART 4: 辅助
# ═══════════════════════════════════════════════════════════════════

def _mood_label(mood: float) -> str:
    if mood >= 4:
        return "超开心"
    if mood >= 2:
        return "开心"
    if mood >= 0:
        return "平静"
    if mood >= -2:
        return "有点低落"
    return "难过"


# 全局单例
memory_consolidator = MemoryConsolidator()

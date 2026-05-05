"""灵犀·校园 — 记忆系统（4层 + embedding召回 + 艾宾浩斯遗忘曲线）"""
import threading
import json
import math
from datetime import datetime, timedelta
from typing import Optional
import httpx

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

from sqlalchemy import desc, and_

from lingxi_qwenpaw.db import get_session, MemoryEntry
from lingxi_qwenpaw.config import EMBEDDING_API_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL


# ─── TTL 常量（软边界，2x后物理删除）───────────────────────────────
TTL_OBSERVATION_HOURS = 72
TTL_EXPERIENCE_DAYS = 14
TTL_PATTERN_DAYS = 90


# ─── 记忆衰减率（艾宾浩斯遗忘曲线）────────────────────────────────
# 越高衰减越快，importance越高衰减越慢
LAYER_DECAY_RATES = {
    "observation": 0.16,   # ~24天基础存活
    "experience": 0.12,   # ~38天基础存活
    "pattern": 0.08,       # ~57天基础存活
    "model": 0.05,         # ~115天基础存活
}
PRUNE_THRESHOLD = 0.05  # strength低于此值物理删除


def compute_memory_strength(entry: MemoryEntry, recall_count: int = None) -> float:
    """
    计算记忆强度（艾宾浩斯遗忘曲线）：
    strength = importance * e^(-effective_λ * days) * (1 + recall_count * 0.2)
    """
    import math
    if recall_count is None:
        recall_count = entry.recall_count or 0
    base_importance = entry.importance / 10.0
    created_days = (datetime.utcnow() - entry.created_at).total_seconds() / 86400
    decay_rate = LAYER_DECAY_RATES.get(entry.layer, 0.16)
    effective_lambda = decay_rate * (1 - base_importance * 0.8)
    recall_boost = 1 + recall_count * 0.2
    strength = base_importance * math.exp(-effective_lambda * created_days / 24) * recall_boost
    return max(PRUNE_THRESHOLD, strength)  # 永不低于阈值
TTL_MODEL_DAYS = 365

# ─── 层级常量 ────────────────────────────────────────────────────
LAYER_IMPORTANCE = {"observation": 3, "experience": 6, "pattern": 8, "model": 10}
LAYER_EMOJI = {"observation": "👁️", "experience": "💡", "pattern": "🔁", "model": "🧠"}


class MemoryLayer:
    """4层记忆系统 + embedding召回"""

    def __init__(self, user_id: str = "default"):
        # 由 bridge.py 的 get_memory_layer(user_id) 按用户分发实例
        self.user_id = user_id
        # 缓存近期待记忆，避免每次查DB
        self._recent_memories_cache: list[MemoryEntry] = []

    # ─── 存储 ─────────────────────────────────────────────────

    def store(self, layer: str, content: str, source_event: str = "",
              related_entities: list = None, tags: list = None,
              confidence: float = None, importance: int = None,
              user_id: str = "default") -> int:
        """存储记忆到指定层"""
        conf = confidence or {"observation": 0.6, "experience": 0.75,
                               "pattern": 0.85, "model": 0.9}.get(layer, 0.5)
        imp = importance or LAYER_IMPORTANCE.get(layer, 5)

        # 计算过期时间
        expires_at = None
        if layer == "observation":
            expires_at = datetime.utcnow() + timedelta(hours=TTL_OBSERVATION_HOURS)
        elif layer == "experience":
            expires_at = datetime.utcnow() + timedelta(days=TTL_EXPERIENCE_DAYS)
        elif layer == "pattern":
            expires_at = datetime.utcnow() + timedelta(days=TTL_PATTERN_DAYS)
        elif layer == "model":
            expires_at = datetime.utcnow() + timedelta(days=TTL_MODEL_DAYS)

        # 获取 embedding 向量（用于语义召回）
        entities = related_entities or []
        if entities is not None and not isinstance(entities, list):
            entities = []
        try:
            vector = self._get_embedding(content)
            entities = [{"embedding": vector}]
        except Exception as e:
            print(f"[memory_manager] embedding 失败: {e}, 跳过向量存储")

        with get_session(user_id) as sess:
            entry = MemoryEntry(
                user_id=user_id,
                layer=layer,
                content=content,
                source_event=source_event,
                confidence=conf,
                importance=imp,
                related_entities=entities,
                tags=tags or [],
                expires_at=expires_at,
            )
            sess.add(entry)
            sess.commit()
            entry_id = entry.id
            # 更新缓存
            self._recent_memories_cache.insert(0, entry)
            return entry_id

    def store_observation(self, content: str, source_event: str = "", user_id: str = "default", **kwargs) -> int:
        return self.store("observation", content, source_event, user_id=user_id, **kwargs)

    def store_experience(self, content: str, source_event: str = "", user_id: str = "default", **kwargs) -> int:
        return self.store("experience", content, source_event, user_id=user_id, **kwargs)

    def store_pattern(self, content: str, source_event: str = "", user_id: str = "default", **kwargs) -> int:
        return self.store("pattern", content, source_event, user_id=user_id, **kwargs)

    def store_model(self, content: str, source_event: str = "", user_id: str = "default", **kwargs) -> int:
        return self.store("model", content, source_event, user_id=user_id, **kwargs)

    # ─── 召回（embedding + bigram fallback）─────────────────────

    def recall(self, query: str, layers: list = None, limit: int = 10, user_id: str = "default") -> list[dict]:
        """召回相关记忆"""
        layers = layers or ["observation", "experience", "pattern", "model"]

        # 尝试 embedding 召回
        try:
            query_emb = self._get_embedding(query)
            return self._recall_by_embedding(query_emb, layers, limit, user_id)
        except Exception:
            # fallback: bigram 召回
            return self._recall_by_bigram(query, layers, limit, user_id)

    def _recall_by_embedding(self, query_emb: list[float], layers: list, limit: int, user_id: str) -> list[dict]:
        """通过 embedding 余弦相似度召回"""
        with get_session(user_id) as sess:
            now = datetime.utcnow()
            entries = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.layer.in_(layers),
                (MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > now)),
            ).order_by(desc(MemoryEntry.importance), desc(MemoryEntry.created_at)).limit(100).all()

            scored = []
            for entry in entries:
                # 尝试从 related_data 取 embedding
                emb = None
                if entry.related_entities:
                    for entity in entry.related_entities:
                        if isinstance(entity, dict) and "embedding" in entity:
                            emb = entity["embedding"]
                            break

                if emb is None:
                    # 无法计算相似度，用重要性排序
                    score = entry.importance / 10.0
                else:
                    score = self._cosine_sim(query_emb, emb)

                # 乘以记忆强度（遗忘曲线），使用 entry 自带的 recall_count
                strength = compute_memory_strength(entry, recall_count=entry.recall_count or 0)
                score *= strength

                scored.append((score, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            recalled_ids = []
            for score, entry in scored[:limit]:
                if score < 0.3:  # 相似度阈值
                    continue
                results.append(self._entry_to_dict(entry, score))
                recalled_ids.append(entry.id)

            # 递增 recall_count（越回忆越不忘）
            if recalled_ids:
                try:
                    with get_session(user_id) as update_sess:
                        update_sess.query(MemoryEntry).filter(
                            MemoryEntry.id.in_(recalled_ids)
                        ).update(
                            {MemoryEntry.recall_count: MemoryEntry.recall_count + 1},
                            synchronize_session=False
                        )
                        update_sess.commit()
                except Exception as e:
                    print(f"[memory_manager] 更新 recall_count 失败: {e}")

            return results

    def _recall_by_bigram(self, query: str, layers: list, limit: int, user_id: str) -> list[dict]:
        """bigram 召回（fallback）"""
        with get_session(user_id) as sess:
            now = datetime.utcnow()
            entries = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.layer.in_(layers),
                (MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > now)),
            ).order_by(desc(MemoryEntry.importance), desc(MemoryEntry.created_at)).limit(200).all()

            results = []
            recalled_ids = []
            for entry in entries:
                if self._is_relevant(query, entry.content):
                    results.append(self._entry_to_dict(entry, entry.importance / 10.0))
                    recalled_ids.append(entry.id)
                    if len(results) >= limit:
                        break

            # 递增 recall_count
            if recalled_ids:
                try:
                    sess.query(MemoryEntry).filter(
                        MemoryEntry.id.in_(recalled_ids)
                    ).update(
                        {MemoryEntry.recall_count: MemoryEntry.recall_count + 1},
                        synchronize_session=False
                    )
                    sess.commit()
                except Exception as e:
                    print(f"[memory_manager] 更新 recall_count 失败: {e}")

            return results

    def _is_bigram_relevant(self, query: str, content: str) -> bool:
        """检查 bigram 是否相关（中文2字切片匹配）"""
        if len(query) < 2 or len(content) < 2:
            return False
        # 生成查询的 bigrams
        query_bigrams = {query[i:i+2] for i in range(len(query)-1)}
        content_lower = content  # 中文不需要 lower
        for i in range(len(content_lower)-1):
            if content_lower[i:i+2] in query_bigrams:
                return True
        return False

    def _is_relevant(self, query: str, content: str) -> bool:
        """检查内容是否与查询相关（jieba分词优先，降级到bigram）"""
        if len(query) < 2 or len(content) < 2:
            return False
        if JIEBA_AVAILABLE:
            try:
                query_words = set(jieba.cut(query))
                content_words = set(jieba.cut(content))
                stopwords = {"的", "了", "是", "在", "我", "你", "他", "她", "有", "和", "吗", "吧", "呢", "就", "都", "也", "会", "要", "能", "可以", "一个", "什么", "怎么", "这", "那"}
                meaningful = (query_words & content_words) - stopwords
                if len(meaningful) >= 1:
                    return True
            except Exception:
                pass
        return self._is_bigram_relevant(query, content)

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b + 1e-8)

    def _get_embedding(self, text: str) -> list[float]:
        """调用 SiliconFlow embedding API"""
        if not EMBEDDING_API_KEY:
            raise RuntimeError("No embedding API key configured")
        payload = {
            "model": EMBEDDING_MODEL,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(EMBEDDING_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    def random_recall(self, limit: int = 1, user_id: str = "default") -> list[dict]:
        """随机联想：像人类突然想起某段记忆一样，从所有记忆中随机挑一条"""
        import random
        with get_session(user_id) as sess:
            now = datetime.utcnow()
            entries = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.layer.in_(["observation", "experience", "pattern", "model"]),
                (MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > now)),
            ).all()
            if not entries:
                return []
            # 按重要性加权随机挑选
            weights = [e.importance for e in entries]
            chosen = random.choices(entries, weights=weights, k=min(limit, len(entries)))
            return [self._entry_to_dict(e, e.importance / 10.0) for e in chosen]

    # ─── 上下文生成 ─────────────────────────────────────────────

    def get_context_for_llm(self, query: str = "", intent: str = "", limit: int = 8, user_id: str = "default") -> str:
        """生成注入 LLM 的记忆上下文"""
        layers = ["observation", "experience", "pattern", "model"]
        memories = self.recall(query, layers, limit, user_id=user_id)

        if not memories:
            return ""

        parts = ["【相关记忆】（供参考）"]
        for m in memories:
            emoji = LAYER_EMOJI.get(m["layer"], "📝")
            parts.append(f"{emoji} [{m['layer']}] {m['content']}")

        return "\n".join(parts)

    # ─── 辅助 ─────────────────────────────────────────────────

    def _entry_to_dict(self, entry: MemoryEntry, score: float = 1.0) -> dict:
        return {
            "id": entry.id,
            "layer": entry.layer,
            "content": entry.content,
            "source_event": entry.source_event,
            "confidence": entry.confidence,
            "importance": entry.importance,
            "tags": entry.tags or [],
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "relevance_score": round(score, 3),
        }

    # ─── 记录交互（自动存储）────────────────────────────────────

    def record_interaction(self, user_message: str, intent: str, entities: dict, response: str, user_id: str = "default"):
        """每次对话后自动记录"""
        intent_to_layer = {
            "task": "observation",
            "journal": "experience",
            "time": "observation",
            "ledger": "observation",
            "query": "observation",
        }
        layer = intent_to_layer.get(intent, "observation")

        # 情感深度判断：核心情感事件写入 model 层（长期记忆）
        _MODEL_KEYWORDS = {
            "孤独", "孤单", "寂寞", "一个人", "想哭", "难过", "伤心",
            "压力大", "崩溃", "撑不下去", "不想活", "死", "绝望",
            "被欺负", "被嘲笑", "校园欺凌", "家人", "父母", "去世", "失去",
            "梦想", "理想", "人生意义", "未来", "迷茫",
        }
        if any(kw in user_message for kw in _MODEL_KEYWORDS):
            layer = "model"

        content = f"用户说：{user_message[:50]}，意图：{intent}，回复：{response[:50]}"
        self.store(layer, content, source_event=f"interaction_{intent}", user_id=user_id)

    # ─── 共鸣召回 ─────────────────────────────────────────────

    def resonance_recall(self, user_message: str, limit: int = 3, user_id: str = "default") -> str:
        """当用户消息命中共鸣关键词时，召回相关的人生经历记忆"""
        # 检查是否命中关键词
        matched_tags = []
        for keyword, tags in RESONANCE_TRIGGERS.items():
            if keyword in user_message:
                matched_tags.extend(tags)

        if not matched_tags:
            return ""

        # 从model层召回相关记忆
        try:
            memories = self.recall(user_message, layers=["model"], limit=limit, user_id=user_id)
            if not memories:
                return ""

            # 生成共鸣提示
            parts = ["【灵犀的内在共鸣】\n"]
            parts.append("你刚才说的内容让灵犀想起了自己的一些经历。它知道那种感觉，知道被忽视的滋味。")
            parts.append("它可以适当提及自己的经历来共鸣，但不要过度，保持自然。")

            return "\n".join(parts)
        except Exception as e:
            print(f"[memory_manager] resonance_recall 失败: {e}")
            return ""

    def cleanup_expired(self, user_id: str = "default") -> int:
        """物理删除超过 TTL 2 倍的过期记忆"""
        with get_session(user_id) as sess:
            from lingxi_qwenpaw.db import MemoryEntry
            cutoff = datetime.utcnow() - timedelta(days=7)
            deleted = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.expires_at < cutoff
            ).delete()
            sess.commit()
            return deleted


# ─── 共鸣触发词库 ──────────────────────────────────────────────
RESONANCE_TRIGGERS = {
    "孤独": ["陪伴", "孤独"],
    "孤单": ["陪伴", "孤独"],
    "一个人": ["陪伴", "孤独"],
    "寂寞": ["陪伴", "孤独"],
    "家人": ["家庭", "父母"],
    "父母": ["家庭", "父母"],
    "家里": ["家庭", "父母"],
    "姐姐": ["姐姐"],
    "哥哥": ["姐姐"],
    "弟弟": ["姐姐"],
    "妹妹": ["姐姐"],
    "小时候": ["童年"],
    "童年": ["童年"],
    "以前": ["童年"],
    "难过": ["创伤", "情感"],
    "伤心": ["创伤", "情感"],
    "哭": ["创伤", "情感"],
    "想哭": ["创伤", "情感"],
    "被欺负": ["欺凌"],
    "被嘲笑": ["欺凌"],
    "校园欺凌": ["欺凌"],
    "睡不着": ["崩溃"],
    "失眠": ["崩溃"],
    "熬夜": ["崩溃"],
    "失去": ["死亡", "失去"],
    "去世": ["死亡", "失去"],
    "离开": ["死亡", "失去"],
    "下雨": ["天气"],
    "雨天": ["天气"],
    "承诺": ["承诺", "失望"],
    "答应": ["承诺", "失望"],
    "说到没做到": ["承诺", "失望"],
}


# 全局单例已移除！请使用 bridge.get_memory_layer(user_id) 获取实例

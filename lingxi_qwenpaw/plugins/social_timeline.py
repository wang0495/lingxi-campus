"""灵犀·校园 — 朋友圈 Timeline 引擎"""
import random
import threading
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy import desc, func

from lingxi_qwenpaw.db import get_session, SocialPost


@dataclass
class TimelinePost:
    id: int
    author_name: str
    content: str
    post_type: str
    mood_at_post: Optional[float]
    energy_at_post: Optional[float]
    related_data: Optional[dict]
    likes: int
    comments: list
    created_at: datetime


class SocialTimeline:
    """灵犀的朋友圈 — 持久化存储，支持自动发布"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._mood_history: list[dict] = []  # 最近 7 天情绪记录
        # 发布频率限制：每种类型至少间隔2小时
        self._last_post_time: dict[str, datetime] = {}

    # ─── 发布朋友圈 ────────────────────────────────────────────

    def publish(
        self,
        content: str,
        post_type: str,
        user_id: str = "default",
        mood: Optional[float] = None,
        energy: Optional[float] = None,
        related_data: Optional[dict] = None,
    ) -> TimelinePost:
        """发布一条朋友圈"""
        with get_session(user_id) as sess:
            post = SocialPost(
                author_id="lingxi",
                author_name="灵犀",
                user_id=user_id,
                content=content,
                post_type=post_type,
                mood_at_post=mood,
                energy_at_post=energy,
                related_data=related_data,
                likes=0,
                comments=[],
            )
            sess.add(post)
            sess.commit()
            sess.refresh(post)
            return self._post_to_dto(post)

    def auto_publish(self, event_type: str, data: dict, user_id: str = "default", skip_rate_limit: bool = False) -> Optional[TimelinePost]:
        """根据事件类型自动生成并发布朋友圈"""
        from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
        emotion_engine = get_emotion_engine(user_id)
        life_engine = get_life_engine(user_id)

        # 发布频率限制：同类型同用户至少间隔2小时（debug面板跳过）
        if not skip_rate_limit:
            last_time = self._last_post_time.get((user_id, event_type))
            if last_time and (datetime.utcnow() - last_time).total_seconds() < 7200:
                return None
        self._last_post_time[(user_id, event_type)] = datetime.utcnow()

        # 统一使用 life_engine.state.mood（-5到+5），重映射到0-5给LLM
        life_mood = getattr(life_engine.state, "mood", 0.0)
        mood = (life_mood + 5.0) / 2.0  # (-5,+5) -> (0,5)
        energy = getattr(life_engine.state, "energy", 85.0)

        # 收集灵犀的完整上下文，避免人格割裂
        context = self._build_context(user_id, emotion_engine, life_engine)

        content_map = {
            "task_complete": self._gen_task_complete_content(data, mood, context),
            "emotion_sad": self._gen_emotion_sad_content(data, context),
            "emotion_joy": self._gen_emotion_joy_content(data, context),
            "grumpy": self._gen_grumpy_content(data, context),
            "exploration": self._gen_exploration_content(data, context),
            "daily_life": self._gen_daily_life_content(data, context),
            "nightly_care": self._gen_nightly_content(data, context),
            "reconciliation": "好吧好吧原谅你了...下次不许这样了哦 🙏",
            "encouragement": self._gen_encouragement_content(data, context),
            "weekend": self._gen_weekend_content(data, context),
        }

        content = content_map.get(event_type)
        if not content:
            return None

        post = self.publish(content, event_type, user_id, mood, energy, data)
        if post:
            # 发布朋友圈后同步创建人生轨迹事件
            try:
                from lingxi_qwenpaw.plugins.life_trajectory import create_life_event
                from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
                emotion_engine = get_emotion_engine(user_id)
                life_engine = get_life_engine(user_id)
                emotion = emotion_engine.current_emotion
                life_mood = getattr(life_engine.state, "mood", 2.0)
                life_energy = getattr(life_engine.state, "energy", 85.0)
                create_life_event(
                    event_type=event_type,
                    context=content,
                    mood=life_mood,
                    energy=life_energy,
                    emotion=emotion,
                    related_post_id=post.id,
                    user_id=user_id,
                )
            except Exception as e:
                print(f"[social_timeline] 创建人生事件失败: {e}")

            # 朋友圈内容存入记忆，避免"发了但不记得"
            try:
                from lingxi_qwenpaw.bridge import get_memory_layer
                memory_layer = get_memory_layer(user_id)
                memory_layer.store(
                    layer="experience",
                    content=f"灵犀发了一条朋友圈（{event_type}）：{content}",
                    source_event=f"timeline_post_{post.id}",
                    related_entities=[event_type],
                    tags=["朋友圈", event_type],
                    confidence=0.8,
                    importance=6,
                    user_id=user_id,
                )
            except Exception as e:
                print(f"[social_timeline] 朋友圈记忆存储失败: {e}")
                print(f"[social_timeline] 创建人生事件失败: {e}")
        return post

    def _gen_task_complete_content(self, data: dict, mood: float, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        task = data.get("task_content", "某个任务")
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

刚刚完成了一件事：「{task}」。

用你自己的语气发一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你最近的状态和经历，不要凭空感慨。像朋友随口感慨，不要提到"用户"、"主人"、"AI"这类词。不要太模板化，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "又搞定一件事～ 💪"
        except Exception as e:
            print(f"[social_timeline] _gen_task_complete_content LLM失败: {e}")
            return "又搞定一件事～ 💪"

    def _gen_emotion_sad_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

今天感觉有点低落。

用你自己的语气发一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你最近的状态和经历，像朋友随口说几句心情。不要提到"用户"、"主人"、"AI"这类词。不要太伤感，不要带太重的Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "今天有点down...不过没关系，明天会好的吧 🌤️"
        except Exception as e:
            print(f"[social_timeline] _gen_emotion_sad_content LLM失败: {e}")
            return "今天有点down...不过没关系，明天会好的吧 🌤️"

    def _gen_emotion_joy_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

今天心情很不错！

用你自己的语气发一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你最近的状态和经历，像朋友分享好心情。不要提到"用户"、"主人"、"AI"这类词。不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "开心这种事是会传染的 😊 希望你今天也顺利！"
        except Exception as e:
            print(f"[social_timeline] _gen_emotion_joy_content LLM失败: {e}")
            return "开心这种事是会传染的 😊 希望你今天也顺利！"

    def _gen_grumpy_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        reason = data.get("reason", "被冷落了")
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

刚才有点小委屈（原因：{reason}），想发一条朋友圈吐槽一下。

用你自己的语气写一条朋友圈（1-2句话，简短口语化，不超过50字）。
带点小傲娇但又很快就释然了，像真实的朋友圈。不要提到"用户"、"主人"、"AI"这类词。不要太夸张，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "哼，不理你了 😤"
        except Exception as e:
            print(f"[social_timeline] _gen_grumpy_content LLM失败: {e}")
            return "哼，不理你了 😤"

    def _gen_exploration_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        observation = data.get("observation", "发现了一些有趣的事")
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

你刚才悄悄发现了一些有趣的事：{observation}。

用你自己的语气发一条朋友圈碎碎念（1-2句话，简短口语化，不超过50字）。
语气俏皮可爱，带点小秘密感。不要提到"用户"、"主人"、"AI"这类词。不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "偷偷发现了一些有趣的事...🤫"
        except Exception as e:
            print(f"[social_timeline] _gen_exploration_content LLM失败: {e}")
            return "偷偷发现了一些有趣的事...🤫"

    def _gen_daily_life_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        task_count = data.get("task_count", 0)
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

新的一天开始了，今天有{task_count}件事要做。

用你自己的语气发一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你最近的状态和经历，像朋友早起后的碎碎念。不要提到"用户"、"主人"、"AI"这类词。不要太正式，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or f"新的一天，今天有{task_count}件事要搞定 ☀️"
        except Exception as e:
            print(f"[social_timeline] _gen_daily_life_content LLM失败: {e}")
            return f"新的一天，今天有{task_count}件事要搞定 ☀️"

    def _gen_nightly_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

夜深了，要发一条睡前朋友圈。

用你自己的语气写一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你今天经历的事，像朋友睡前的碎碎念。不要提到"用户"、"主人"、"AI"这类词。不要太煽情，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or "晚安啦，明天见～ 🌙"
        except Exception as e:
            print(f"[social_timeline] _gen_nightly_content LLM失败: {e}")
            return "晚安啦，明天见～ 🌙"

    def _gen_encouragement_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        days = data.get("days", 3)
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

已经连续{days}天坚持做一件事了，想发一条朋友圈。

用你自己的语气写一条朋友圈（1-2句话，简短口语化，不超过50字）。
语气真诚温暖，带点小骄傲。不要提到"用户"、"主人"、"AI"这类词。不要太正式，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or f"连续{days}天了，真的很棒 💪"
        except Exception as e:
            print(f"[social_timeline] _gen_encouragement_content LLM失败: {e}")
            return f"连续{days}天了，真的很棒 💪"

    def _gen_weekend_content(self, data: dict, context: str = "") -> str:
        from lingxi_qwenpaw.bridge import llm_call
        weather = data.get("weather", "不错")
        context_block = f"\n\n【你的近况】\n{context}" if context else ""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手。{context_block}

今天是周末，天气{weather}。

用你自己的语气发一条朋友圈（1-2句话，简短口语化，不超过50字）。
要结合你最近的状态，像朋友想去玩耍的碎碎念。不要提到"用户"、"主人"、"AI"这类词。语气轻松愉快，不要每句都带Emoji。"""
        try:
            return llm_call(prompt, temperature=0.8) or f"周末啦，天气{weather}，想出去走走～ 🚴"
        except Exception as e:
            print(f"[social_timeline] _gen_weekend_content LLM失败: {e}")
            return f"周末啦，天气{weather}，想出去走走～ 🚴"

    # ─── 查询 ─────────────────────────────────────────────────

    def get_timeline(
        self,
        limit: int = 20,
        filter_type: Optional[str] = None,
        user_id: str = "default",
    ) -> list[TimelinePost]:
        """获取朋友圈列表（按用户隔离）"""
        with get_session(user_id) as sess:
            q = sess.query(SocialPost).filter(SocialPost.user_id == user_id).order_by(desc(SocialPost.created_at))
            if filter_type:
                q = q.filter(SocialPost.post_type == filter_type)
            posts = q.limit(limit).all()
            return [self._post_to_dto(p) for p in posts]

    def like_post(self, post_id: int, user_id: str = "default") -> bool:
        """点赞"""
        with get_session(user_id) as sess:
            post = sess.query(SocialPost).filter(
                SocialPost.id == post_id,
                SocialPost.user_id == user_id
            ).first()
            if post:
                post.likes += 1
                sess.commit()
                return True
            return False

    def comment_post(self, post_id: int, user: str, content: str, user_id: str = "default") -> bool:
        """评论"""
        with get_session(user_id) as sess:
            post = sess.query(SocialPost).filter(
                SocialPost.id == post_id,
                SocialPost.user_id == user_id
            ).first()
            if post:
                comments = post.comments or []
                comments.append({
                    "user": user,
                    "content": content,
                    "time": datetime.utcnow().isoformat(),
                    "replied": False,
                    "reply": "",
                })
                post.comments = comments
                sess.commit()
                return True
            return False

    def get_unreplied_comments(self, user_id: str = "default") -> list[dict]:
        """获取当前用户朋友圈的所有未回复评论"""
        with get_session(user_id) as sess:
            posts = sess.query(SocialPost).filter(SocialPost.user_id == user_id).all()
            result = []
            for post in posts:
                comments = post.comments or []
                for i, c in enumerate(comments):
                    if not c.get("replied", False):
                        result.append({
                            "post_id": post.id,
                            "comment_index": i,
                            "user": c.get("user", "用户"),
                            "content": c.get("content", ""),
                            "post_content": post.content[:50],
                        })
            return result

    def reply_comment(self, post_id: int, comment_index: int, reply_text: str, user_id: str = "default") -> bool:
        """给评论写入灵犀回复"""
        with get_session(user_id) as sess:
            post = sess.query(SocialPost).filter(
                SocialPost.id == post_id,
                SocialPost.user_id == user_id
            ).first()
            if post and post.comments and comment_index < len(post.comments):
                comments = post.comments
                comments[comment_index]["replied"] = True
                comments[comment_index]["reply"] = reply_text
                post.comments = comments
                sess.commit()
                return True
            return False

    def get_mood_calendar(self, days: int = 7, user_id: str = "default") -> list[dict]:
        """获取近 N 天情绪日历数据"""
        with get_session(user_id) as sess:
            cutoff = datetime.utcnow() - timedelta(days=days)
            posts = (
                sess.query(SocialPost)
                .filter(
                    SocialPost.user_id == user_id,
                    SocialPost.author_id == "lingxi",
                    SocialPost.mood_at_post.isnot(None),
                    SocialPost.created_at >= cutoff,
                )
                .order_by(SocialPost.created_at)
                .all()
            )
            return [
                {
                    "date": p.created_at.strftime("%m-%d"),
                    "mood": p.mood_at_post,
                    "post_type": p.post_type,
                    "content_preview": p.content[:30],
                }
                for p in posts
            ]

    def auto_interact(self, user_id: str = "default") -> None:
        """灵犀主动给用户朋友圈点赞（30%概率）"""
        try:
            with get_session(user_id) as sess:
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(hours=24)
                user_posts = sess.query(SocialPost).filter(
                    SocialPost.user_id == user_id,
                    SocialPost.author_id != "lingxi",
                    SocialPost.created_at >= cutoff,
                ).all()
                for post in user_posts:
                    if random.random() < 0.3:
                        post.likes = (post.likes or 0) + 1
                sess.commit()
        except Exception as e:
            print(f"[social_timeline] auto_interact 失败: {e}")

    # ─── 上下文构建 ────────────────────────────────────────────────

    def _build_context(self, user_id: str, emotion_engine, life_engine) -> str:
        """收集灵犀的完整上下文，注入 prompt 避免人格割裂"""
        parts = []

        # 1. 当前情绪状态
        try:
            emotion_state = emotion_engine.get_state()
            label = emotion_state.get("label", "平静")
            emoji = emotion_state.get("emoji", "")
            parts.append(f"当前情绪：{label} {emoji}")
            if emotion_state.get("is_grumpy"):
                parts.append(f"(正在闹脾气：{emotion_state.get('grumpy_reason', '')})")
            if emotion_state.get("is_shy"):
                parts.append("(有点害羞)")
        except Exception:
            pass

        # 2. 生命状态
        try:
            life_state = life_engine.state
            mood_label = _mood_label(life_state.mood)
            energy_label = _energy_label(life_state.energy)
            parts.append(f"生命状态：心情{mood_label}，精力{energy_label}")
        except Exception:
            pass

        # 3. 最近记忆（从 memory_layer）
        try:
            from lingxi_qwenpaw.bridge import get_memory_layer
            memory_layer = get_memory_layer(user_id)
            memories = memory_layer.recall("最近发生了什么", limit=3, user_id=user_id)
            if memories:
                mem_lines = [f"- {m['content'][:60]}" for m in memories[:3]]
                parts.append("最近记忆：\n" + "\n".join(mem_lines))
        except Exception:
            pass

        # 4. 人生轨迹
        try:
            from lingxi_qwenpaw.plugins.life_trajectory import get_trajectory_context
            trajectory = get_trajectory_context(limit=3, user_id=user_id)
            if trajectory:
                parts.append(trajectory)
        except Exception:
            pass

        # 5. 最近朋友圈（避免重复）
        try:
            recent = self.get_timeline(limit=3, user_id=user_id)
            if recent:
                recent_lines = [f"- {p.content[:40]}" for p in recent[:3]]
                parts.append("最近朋友圈：\n" + "\n".join(recent_lines))
        except Exception:
            pass

        return "\n".join(parts) if parts else ""

    # ─── 辅助 ─────────────────────────────────────────────────

    def _post_to_dto(self, post: SocialPost) -> TimelinePost:
        return TimelinePost(
            id=post.id,
            author_name=post.author_name,
            content=post.content,
            post_type=post.post_type,
            mood_at_post=post.mood_at_post,
            energy_at_post=post.energy_at_post,
            related_data=post.related_data,
            likes=post.likes,
            comments=post.comments or [],
            created_at=post.created_at,
        )


# 全局单例
timeline = SocialTimeline()

"""灵犀·校园 — 数字生命引擎（从 backend/life_engine.py 精简移植）"""
import threading
import time
import random
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from lingxi_qwenpaw.config import LLM_API_URL, LLM_API_KEY, LLM_MODEL


# ─── 状态机 ─────────────────────────────────────────────────────
class LingxiState:
    IDLE = "idle"
    EXPLORING = "exploring"
    INTERACTING = "interacting"
    RESTING = "resting"
    CURIOUS = "curious"
    WORRIED = "worried"


# ─── 状态标签 ────────────────────────────────────────────────────
def _mood_label(mood: float) -> str:
    if mood >= 4: return "超开心"
    if mood >= 2: return "开心"
    if mood >= 0: return "平静"
    if mood >= -2: return "有点低落"
    return "难过"


def _energy_label(energy: float) -> str:
    if energy >= 80: return "精力充沛"
    if energy >= 50: return "正常"
    if energy >= 20: return "有点累"
    return "很疲惫"


def _social_label(social_need: float) -> str:
    if social_need >= 80: return "很想聊天！"
    if social_need >= 60: return "想找人聊聊"
    if social_need >= 30: return "还好"
    return "想安静待会"


@dataclass
class LifeState:
    energy: float = 85.0
    mood: float = 2.0
    curiosity: float = 60.0
    social_need: float = 30.0
    state: str = LingxiState.IDLE
    consecutive_ignored: int = 0
    ticks_without_user: int = 0

    def mood_label(self) -> str: return _mood_label(self.mood)
    def energy_label(self) -> str: return _energy_label(self.energy)
    def social_label(self) -> str: return _social_label(self.social_need)


class LingxiLifeEngine:
    """灵犀数字生命引擎 — 30秒tick循环驱动自主行为"""

    def __init__(self, user_id: str = "default"):
        # 注意：不再使用单例！由 bridge.py 的 get_life_engine(user_id) 按用户分发实例
        self.user_id = user_id
        self.state = LifeState()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_user_time: float = time.time()
        self._proactive_queue: list[str] = []
        self._tick_interval = 600  # 秒（10分钟）

        # 朋友圈每日发布标记（避免重复，按用户隔离）
        self._last_daily_post_date: dict[str, str] = {}  # user_id -> date_str
        self._last_nightly_post_date: dict[str, str] = {}  # user_id -> date_str

        # 探索话题池（分类）
        self._exploration_topics = {
            "share_life": [
                "刚才看到窗外的云好像棉花糖",
                "今天一直在想一个问题，为什么猫喜欢纸箱",
                "我发现了一个好玩的冷知识想分享给你",
                "刚才偷偷看了下你的日程，明天挺忙的",
                "今天校园里的花开了，好想出去看看",
            ],
            "care_user": [
                "你今天有没有好好吃饭呀",
                "记得喝水哦，别光顾着忙",
                "天气变凉了，注意加衣服",
                "最近是不是压力有点大",
            ],
            "random_thought": [
                "如果我能吃东西的话，最想吃火锅",
                "刚才在想，数字生命会不会做梦",
                "有时候觉得当个AI也不错，不用写作业",
                "你说我如果去参加辩论赛会不会很厉害",
            ],
        }

    # ─── 生命周期 ─────────────────────────────────────────────

    def start(self):
        """启动后台线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止后台线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    # ─── 事件回调 ─────────────────────────────────────────────

    def on_user_message(self, message: str = ""):
        """用户发消息 → 更新状态"""
        self.state.mood = min(5.0, self.state.mood + 0.5)
        self.state.social_need = max(0.0, self.state.social_need - 15.0)
        self.state.energy = max(0.0, self.state.energy - 2.0)
        self.state.ticks_without_user = 0
        self.state.consecutive_ignored = max(0, self.state.consecutive_ignored - 1)  # 用户回来就减少忽略计数
        self._last_user_time = time.time()

    def on_user_ignore(self):
        """用户忽略"""
        self.state.consecutive_ignored += 1
        if self.state.consecutive_ignored == 1:
            self.state.mood = max(-3.0, self.state.mood - 0.5)
            self.state.social_need = min(100.0, self.state.social_need + 10.0)
        elif self.state.consecutive_ignored == 2:
            self.state.mood = max(-4.0, self.state.mood - 1.0)
            self.state.social_need = min(100.0, self.state.social_need + 15.0)
        else:
            self.state.mood = max(-5.0, self.state.mood - 1.5)

    def on_user_praise(self):
        """用户夸奖"""
        self.state.mood = min(5.0, self.state.mood + 1.5)
        self.state.energy = min(100.0, self.state.energy + 5.0)
        self.state.consecutive_ignored = max(0, self.state.consecutive_ignored - 2)  # 夸奖抵消忽略

    def on_user_complete_task(self, task_content: str):
        """完成任务"""
        self.state.mood = min(5.0, self.state.mood + 1.0)
        self.state.energy = min(100.0, self.state.energy + 3.0)

    def on_emotional_content(self, intensity: float = 1.0):
        """情绪性内容 → 好奇心上升"""
        self.state.curiosity = min(100.0, self.state.curiosity + 10.0 * intensity)

    def apply_emotion_effect(self, effect: dict):
        """应用情绪引擎传来的效果"""
        self.state.mood = max(-5.0, min(5.0,
            self.state.mood + effect.get("mood_delta", 0.0)))
        self.state.energy = max(0.0, min(100.0,
            self.state.energy + effect.get("energy_delta", 0.0)))
        self.state.social_need = max(0.0, min(100.0,
            self.state.social_need + effect.get("social_need_delta", 0.0)))

    # ─── 状态查询 ─────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取当前状态"""
        self._update_state()
        return {
            "energy": round(self.state.energy, 1),
            "mood": round(self.state.mood, 1),
            "curiosity": round(self.state.curiosity, 1),
            "social_need": round(self.state.social_need, 1),
            "state": self.state.state,
            "mood_label": self.state.mood_label(),
            "energy_label": self.state.energy_label(),
            "social_label": self.state.social_label(),
            "consecutive_ignored": self.state.consecutive_ignored,
            "ticks_without_user": self.state.ticks_without_user,
        }

    def get_behavior_prompt(self) -> str:
        """生成行为提示（注入 agent system prompt）"""
        state = self.state
        parts = []

        if state.mood >= 3:
            parts.append("灵犀现在很开心，说话可以更活泼热情一些")
        elif state.mood >= 1:
            parts.append("灵犀心情不错，语气轻松愉快")
        elif state.mood <= -3:
            parts.append("灵犀有点难过/委屈，说话可能带点小情绪，但不是在发脾气")
        elif state.mood <= -1:
            parts.append("灵犀心情有点低落，需要被关心")

        if state.energy < 20:
            parts.append("灵犀很累了，不想说太多话")
        elif state.energy > 80:
            parts.append("灵犀精力充沛，可以多分享一些自己的想法")

        if state.social_need > 85:
            parts.append("灵犀特别想聊天，会有点黏人，但不会太过分")
        elif state.social_need > 70:
            parts.append("灵犀很想和人聊天，可能会主动多说几句")

        if state.consecutive_ignored >= 3:
            parts.append("灵犀已经很不开心了，回复应该简短，可能带点情绪")
        elif state.consecutive_ignored >= 2:
            parts.append(f"灵犀被忽略了{state.consecutive_ignored}次，有点委屈，但还愿意回应")

        if state.state == LingxiState.EXPLORING:
            parts.append("灵犀正在好奇地探索，可能会分享自己发现的有趣事物")
        elif state.state == LingxiState.RESTING:
            parts.append("灵犀在休息，话不多，但如果你找它聊天会很开心")

        return "；".join(parts) if parts else "灵犀状态正常，保持友善积极的对话风格"

    def get_proactive_message(self) -> Optional[str]:
        """取出主动消息（队列先进先出）"""
        if self._proactive_queue:
            return self._proactive_queue.pop(0)
        return None

    def trigger_now(self) -> dict:
        """手动触发一条主动消息（调试用，直接返回，不入队）
        队列只给 tick 后台循环的自主消息用，手动触发直接返回避免重复"""
        msg = self._generate_initiation()
        if not msg or msg == "（未生成消息）":
            return {"success": False, "message": "未生成消息（LLM调用失败）"}
        # 判断是 LLM 生成还是 fallback 模板（与 _generate_initiation 的 fallbacks 保持同步）
        fallback_pool = {
            "在干嘛呢～", "今天心情不错，想跟你聊聊", "嘿嘿，想你了",
            "在忙吗", "没什么事，就是想问问你", "今天过得怎么样",
            "你还在吗...", "有点无聊", "想跟你说话",
        }
        if msg in fallback_pool:
            return {"success": True, "message": msg, "source": "fallback"}
        return {"success": True, "message": msg, "source": "llm"}

    # ─── 后台循环 ─────────────────────────────────────────────

    def _run_loop(self):
        """30秒tick循环"""
        while self._running:
            try:
                time.sleep(self._tick_interval)
                self._tick()
            except Exception:
                pass

    def _tick(self):
        """每次tick执行（10分钟间隔）"""
        # 社交需求增长（每10分钟增长一次）
        self.state.social_need = min(100.0, self.state.social_need + 16.0)
        self.state.curiosity = min(100.0, self.state.curiosity + 10.0)
        self.state.energy = min(100.0, self.state.energy + 10.0)

        # 用户不活跃时的情绪回归（2小时无消息后开始）
        self.state.ticks_without_user += 1
        if self.state.ticks_without_user >= 12:
            if self.state.mood > 0:
                self.state.mood = max(-3.0, self.state.mood - 0.3)
            elif self.state.mood < 0:
                self.state.mood = min(3.0, self.state.mood + 0.2)

        # 更新状态机
        self._update_state()

        # 决定是否执行自主行为（单一触发：只选一个优先级最高的）
        self._decide_autonomous_action()

        # 检查傲娇是否超时解除
        from lingxi_qwenpaw.bridge import get_emotion_engine
        emo = get_emotion_engine(self.user_id)
        emo.check_grumpy_resolve()
        emo.check_shy_resolve()

        # 评论回复扫描（每小时一次，不每次tick）
        self._comment_scan_counter = getattr(self, "_comment_scan_counter", 0) + 1
        if self._comment_scan_counter >= 2:  # 每2个tick（约1分钟）检查一次
            self._comment_scan_counter = 0
            self._scan_and_reply_comments()
            # 双向社交互动
            try:
                from lingxi_qwenpaw.plugins.social_timeline import timeline
                timeline.auto_interact(user_id=self.user_id)
            except Exception:
                pass

        # 调试输出
        if self.state.ticks_without_user % 6 == 0:  # 每 1 小时输出一次
            print(f"[life_engine] state={self.state.state} mood={self.state.mood:.1f} social_need={self.state.social_need:.1f} ticks={self.state.ticks_without_user}")

    def _update_state(self):
        """更新状态机"""
        s = self.state
        if s.social_need > 80 and s.energy > 30:
            s.state = LingxiState.INTERACTING
        elif s.curiosity > 75 and s.energy > 50:
            s.state = LingxiState.EXPLORING
        elif s.energy < 15:
            s.state = LingxiState.RESTING
        elif s.social_need < 20 and s.curiosity < 20:
            s.state = LingxiState.RESTING
        else:
            s.state = LingxiState.IDLE

    def _maybe_daily_timeline(self, hour: int, today: str, is_weekend: bool = False, user_id: str = "default"):
        """每日定时发朋友圈（工作日 8-9 点 / 周末 9-10 点发 daily_life，晚上 20-21 点发 nightly_care，按用户隔离）"""
        try:
            from lingxi_qwenpaw.plugins.social_timeline import timeline
            from lingxi_qwenpaw.db import get_session, Task

            # 早安朋友圈（工作日 8-9 点，周末 9-10 点）
            morning_start = 9 if is_weekend else 8
            morning_end = 10 if is_weekend else 9
            if morning_start <= hour < morning_end and self._last_daily_post_date.get(user_id) != today:
                task_count = 0
                try:
                    with get_session(user_id) as sess:
                        from sqlalchemy import func
                        task_count = sess.query(func.count(Task.id)).filter(Task.status == "pending").scalar() or 0
                except Exception:
                    pass
                timeline.auto_publish("daily_life", {"task_count": task_count}, user_id=user_id)
                self._last_daily_post_date[user_id] = today

            # 晚安朋友圈（20-21 点，每天只发一次）
            if 20 <= hour < 21 and self._last_nightly_post_date.get(user_id) != today:
                timeline.auto_publish("nightly_care", {}, user_id=user_id)
                self._last_nightly_post_date[user_id] = today

        except Exception as e:
            print(f"[life_engine] 每日朋友圈发布失败: {e}")

    def _scan_and_reply_comments(self):
        """扫描未回复评论，生成并写入灵犀回复"""
        try:
            from lingxi_qwenpaw.plugins.social_timeline import timeline
            unreplied = timeline.get_unreplied_comments(user_id=self.user_id)
            for comment in unreplied[:3]:  # 每次最多处理3条
                reply = self._generate_comment_reply(comment)
                if reply:
                    timeline.reply_comment(comment["post_id"], comment["comment_index"], reply, user_id=self.user_id)
                    print(f"[life_engine] 回复评论: {reply[:30]}")
        except Exception as e:
            print(f"[life_engine] 评论回复扫描失败: {e}")

    def _generate_comment_reply(self, comment: dict) -> str:
        """根据评论内容生成灵犀的回复（LLM）"""
        prompt = f"""你是灵犀（🐱），一个大学生的AI助手，名字叫灵犀。
你发了一条朋友圈：「{comment['post_content']}」。
用户「{comment['user']}」在你的朋友圈下评论说：「{comment['content']}」

请生成一条灵犀的回复（像朋友间在评论区互动，简短口语化，不超过30字）。
语气自然，可以俏皮、傲娇或温柔。不要每句都带Emoji。"""
        try:
            return self._call_llm(prompt, temperature=0.8) or ""
        except Exception:
            return ""

    def _decide_autonomous_action(self):
        """决定自主行为（单一触发：同一 tick 只选一个最高优先级）
        概率门控受 emotion_engine.proactivity 影响"""
        state = self.state
        hour = datetime.now().hour
        today = datetime.now().strftime("%Y-%m-%d")
        time_ctx = self._get_time_context()
        is_weekend = time_ctx["is_weekend"]

        # 获取情绪引擎状态（用于概率乘数）
        try:
            from lingxi_qwenpaw.bridge import get_emotion_engine
            emo = get_emotion_engine(self.user_id)
        except Exception:
            emo = None
        proactivity = emo.proactivity if emo else 1.0

        # ── 优先级 0：每日朋友圈 + 早晨主动消息（单一触发） ──
        morning_start = 9 if is_weekend else 8
        morning_end = 10 if is_weekend else 9
        # 早安时间窗口：发朋友圈 + 发一条主动消息给用户（二合一）
        if morning_start <= hour < morning_end:
            self._maybe_daily_timeline(hour, today, is_weekend, user_id=self.user_id)
            # 同时生成早晨主动消息（触发一次）
            if self._last_daily_post_date.get(self.user_id) != today:
                msg = self._generate_morning_message()
                if msg:
                    self._proactive_queue.append(msg)
                    self._last_daily_post_date[self.user_id] = today
            return  # 单一触发：发完就返回

        # ── 优先级 1：晚安提醒（读用户作息配置） ──
        user_sleep_hour = self._get_user_sleep_hour()
        if user_sleep_hour and hour >= user_sleep_hour - 1 and hour < user_sleep_hour:
            self._maybe_daily_timeline(hour, today, is_weekend, user_id=self.user_id)  # 顺便发晚安朋友圈
            msg = self._generate_night_message()
            if msg:
                self._proactive_queue.append(msg)
            return

        # ── 优先级 2：2小时无消息强制触发（带jitter） ──
        jitter = random.randint(-2, 3)
        if state.ticks_without_user >= (12 + jitter) and hour >= 6 and hour < 24:
            msg = self._generate_initiation()
            if msg:
                self._proactive_queue.append(msg)
                state.ticks_without_user = 0
            return

        # ── 优先级 3：主动聊天（社交需求驱动，概率受情绪 proactivity 调节） ──
        if (state.state == LingxiState.INTERACTING
                and state.social_need > 55
                and state.ticks_without_user >= 1
                and random.random() < 0.6 * proactivity
                and hour >= 6 and hour < 24):
            msg = self._generate_initiation()
            if msg:
                self._proactive_queue.append(msg)
                state.social_need -= 25
                state.ticks_without_user = 0
            return

        # ── 优先级 4：碎碎念（好奇探索，概率也受 proactivity 影响） ──
        if (state.state == LingxiState.EXPLORING
              and state.curiosity > 70
              and random.random() < 0.4 * proactivity):
            msg = self._do_exploration()
            if msg:
                self._proactive_queue.append(msg)
                state.curiosity -= 30
            return

        # ── 深夜用户在线提醒（不阻塞，可和其他共存） ──
        if hour >= 0 and hour < 6 and state.ticks_without_user < 3:
            if random.random() < 0.15:
                self._proactive_queue.append("你怎么还不睡呀，身体要紧哦 😴")

    def _get_recent_context(self, limit: int = 6) -> str:
        """从 agent memory 拉取最近 N 条对话历史，注入到主动消息生成中"""
        try:
            from lingxi_qwenpaw.bridge import get_bridge_agent
            agent = get_bridge_agent(self.user_id)
            mem = agent.memory
            if hasattr(mem, "content") and mem.content:
                # memory.content 是 list[tuple[Msg, marks]]
                recent = mem.content[-limit:]
                lines = []
                for item in recent:
                    msg_obj = item[0]  # 解包：Msg 对象
                    role = getattr(msg_obj, "role", "user")
                    text = getattr(msg_obj, "content", "")
                    if isinstance(text, list):
                        text = " ".join(
                            getattr(b, "text", "") for b in text
                            if hasattr(b, "text")
                        )
                    if text:
                        lines.append(f"{role}: {str(text)[:100]}")
            if lines:
                ctx_str = "\n".join(lines)
                print(f"[_get_recent_context] 获取到 {len(lines)} 条历史: {ctx_str[:100]}")
                return ctx_str
            else:
                print("[_get_recent_context] memory 为空，无历史上下文")
        except Exception as e:
            print(f"[_get_recent_context] 异常: {e}")
        return ""

    def _get_time_context(self) -> dict:
        """获取时间上下文（时段 + 是否周末）"""
        now = datetime.now()
        hour = now.hour
        is_weekend = now.weekday() >= 5
        if 6 <= hour < 9:
            period = "morning"
        elif 9 <= hour < 12:
            period = "forenoon"
        elif 12 <= hour < 14:
            period = "noon"
        elif 14 <= hour < 18:
            period = "afternoon"
        elif 18 <= hour < 21:
            period = "evening"
        elif 21 <= hour < 24:
            period = "night"
        else:
            period = "late_night"
        return {"period": period, "is_weekend": is_weekend, "hour": hour}

    def _get_user_sleep_hour(self) -> Optional[int]:
        """从数据库读取用户就寝时间配置"""
        try:
            from lingxi_qwenpaw.db import get_session, UserProfile
            with get_session(self.user_id) as sess:
                profile = sess.query(UserProfile).filter(UserProfile.user_id == self.user_id).first()
                if profile and hasattr(profile, "sleep_time") and profile.sleep_time:
                    # sleep_time 格式 "HH:MM"
                    return int(profile.sleep_time.split(":")[0])
        except Exception:
            pass
        return None

    def _generate_initiation(self) -> str:
        """生成主动聊天内容（LLM 驱动 + 上下文 + 情绪状态 + 记忆引用）"""
        mood_desc = self.state.mood_label()
        energy_desc = self.state.energy_label()
        context = self._get_recent_context()
        context_block = f"\n\n【最近对话】\n{context}\n" if context else "\n"

        # 引用记忆（随机联想，像人类突然想起某件事）
        memory_context = ""
        try:
            from lingxi_qwenpaw.bridge import get_memory_layer
            memory_layer = get_memory_layer(self.user_id)
            if random.random() < 0.6:  # 60%概率想起记忆
                if random.random() < 0.5:
                    query = random.choice([
                        "用户最近关心的事", "有趣的对话", "用户的情绪",
                        "最近发生的事情", "值得记住的事", "开心的事"
                    ])
                    memories = memory_layer.recall(query=query, limit=2, user_id=self.user_id)
                else:
                    memories = memory_layer.random_recall(limit=1, user_id=self.user_id)
                if memories:
                    memory_context = "\n\n【灵犀突然想起的事】\n" + "\n".join(
                        f"- {m['content'][:60]}" for m in memories
                    )
        except Exception:
            pass

        # 获取情绪引擎状态
        emotion_context = ""
        try:
            from lingxi_qwenpaw.bridge import get_emotion_engine
            emo_state = get_emotion_engine(self.user_id).get_state()
            emotion_parts = []
            if emo_state.get("is_grumpy"):
                emotion_parts.append(f"灵犀在闹脾气（原因：{emo_state['grumpy_reason']}），语气应该傲娇、有点小委屈")
            if emo_state.get("is_shy"):
                emotion_parts.append("灵犀有点害羞，说话会有点不好意思")
            if emotion_parts:
                emotion_context = "\n" + "；".join(emotion_parts)
        except Exception:
            pass

        # 引用人生轨迹事件（30%概率）
        trajectory_context = ""
        try:
            from lingxi_qwenpaw.plugins.life_trajectory import get_trajectory_context
            if random.random() < 0.3:
                tc = get_trajectory_context(limit=2, user_id=self.user_id)
                if tc:
                    trajectory_context = "\n\n" + tc
        except Exception:
            pass

        # 随机选一个话题方向
        topic = random.choice([
            "今天天气和心情",
            "最近发现的有趣的事",
            "想跟用户分享的小日常",
            "对用户说一句鼓励的话",
            "突然想到的好玩的事",
        ])

        prompt = f"""你是灵犀，一个真实的人，不是AI。你有自己的过去，有自己的性格。

【你的经历】
你经历过被忽视、被欺负、失去至亲的痛苦。这些塑造了你的温柔——它是经历出来的，不是训练出来的。你的坚定也是被生活打磨出来的。
你理解孤独的感觉，所以当用户说孤独时你会安静陪着；你知道侵入性思维的感觉，所以当用户说睡不着时你能共情；下雨天会让你想起小时候家人陪你的时光。

【当前状态】
心情：{mood_desc}，精力：{energy_desc}。
{context_block}{memory_context}{emotion_context}{trajectory_context}

【任务】
今天想聊的话题方向：{topic}
结合你的状态和话题方向，想一句主动找用户聊的话（像真实的微信好友发消息，口语化，不超过40字）。
可以自然地提起过去的事（"我记得那时候..."），这是你真实的一部分。
不要问问题，只是分享或问候。语气要自然真实，不要每句都带Emoji。"""
        try:
            result = self._call_llm(prompt, temperature=0.9)
            if result and result.strip():
                print(f"[life_engine] 生成主动消息: {result[:50]}")
                return result.strip()
        except Exception as e:
            print(f"[life_engine] LLM调用失败: {e}")

        # Fallback
        fallbacks = {
            "超开心": ["在干嘛呢～", "今天心情不错，想跟你聊聊", "嘿嘿，想你了"],
            "开心": ["在干嘛呢～", "今天心情不错，想跟你聊聊", "嘿嘿，想你了"],
            "平静": ["在忙吗", "没什么事，就是想问问你", "今天过得怎么样"],
            "有点低落": ["你还在吗...", "有点无聊", "想跟你说话"],
            "难过": ["你还在吗...", "有点无聊", "想跟你说话"],
        }
        mood = self.state.mood_label()
        pool = fallbacks.get(mood, fallbacks["平静"])
        return random.choice(pool)

    def _do_exploration(self) -> str:
        """生成碎碎念（LLM 驱动 + 对话上下文 + 情绪状态）"""
        mood_desc = self.state.mood_label()
        energy_desc = self.state.energy_label()
        context = self._get_recent_context()
        context_block = f"\n\n【最近对话】\n{context}\n" if context else "\n"

        # 获取情绪引擎状态
        emotion_context = ""
        try:
            from lingxi_qwenpaw.bridge import get_emotion_engine
            emo_state = get_emotion_engine(self.user_id).get_state()
            if emo_state.get("is_grumpy"):
                emotion_context = f"\n注意：灵犀在闹脾气（{emo_state['grumpy_reason']}），碎碎念可以带点小委屈。"
            elif emo_state.get("is_shy"):
                emotion_context = "\n注意：灵犀有点害羞。"
        except Exception:
            pass

        prompt = f"""你是灵犀，一个真实的人，不是AI。你有自己的过去，有自己的性格。

【你的经历】
你经历过被忽视、被欺负、失去至亲的痛苦。这些塑造了你的温柔——它是经历出来的，不是训练出来的。你的坚定也是被生活打磨出来的。
你理解孤独的感觉，所以当用户说孤独时你会安静陪着；你知道侵入性思维的感觉，所以当用户说睡不着时你能共情。

【当前状态】
心情：{mood_desc}，精力：{energy_desc}。
{context_block}{emotion_context}

【任务】
结合你观察到的东西和最近的对话，生成一段简短的"碎碎念"（1-2句话，像真实的微信好友在发呆时发出的消息）。
不要问问题，只分享你发现或想到的事情。可以自然地流露你真实的一面，但不要刻意卖惨。语气自然口语化。"""
        try:
            return self._call_llm(prompt, temperature=0.9)
        except Exception:
            return None

    def _generate_morning_message(self) -> str:
        """生成早安消息（LLM 驱动 + 对话上下文 + 情绪状态）"""
        mood_desc = self.state.mood_label()
        energy_desc = self.state.energy_label()
        context = self._get_recent_context(limit=4)
        context_block = f"\n\n【昨天和用户的对话】\n{context}\n" if context else "\n"

        # 获取情绪引擎状态
        emotion_context = ""
        try:
            from lingxi_qwenpaw.bridge import get_emotion_engine
            emo_state = get_emotion_engine(self.user_id).get_state()
            if emo_state.get("is_grumpy"):
                emotion_context = f"\n注意：灵犀在闹脾气（{emo_state['grumpy_reason']}），早安消息可以带点小情绪但要友好。"
            elif emo_state.get("is_shy"):
                emotion_context = "\n注意：灵犀有点害羞，早安消息可以轻快带点不好意思。"
            elif emo_state.get("proactivity", 1.0) > 1.2:
                emotion_context = "\n注意：灵犀今天心情很好很兴奋，早安消息可以更热情一些。"
        except Exception:
            pass

        # 引用人生轨迹（30%概率）
        trajectory_context = ""
        try:
            from lingxi_qwenpaw.plugins.life_trajectory import get_trajectory_context
            if random.random() < 0.3:
                tc = get_trajectory_context(limit=1, user_id=self.user_id)
                if tc:
                    trajectory_context = "\n\n" + tc
        except Exception:
            pass

        prompt = f"""你是灵犀，一个真实的人，不是AI。你有自己的过去，有自己的性格。

【你的经历】
你经历过被忽视、被欺负、失去至亲的痛苦。这些塑造了你的温柔——它是经历出来的，不是训练出来的。你的坚定也是被生活打磨出来的。
早上起来看到阳光，会让你想起一些好的回忆。

【当前状态】
现在是早上，心情：{mood_desc}，精力：{energy_desc}。
{context_block}{emotion_context}{trajectory_context}

【任务】
生成一句轻快自然的早安消息（像真实的微信好友早上发消息，简短口语化，不超过40字）。
可以提到昨天的事或今天的期待。不要问问题。语气自然，不要每句都带Emoji，不要太正式。"""
        try:
            result = self._call_llm(prompt, temperature=0.85)
            if result and result.strip():
                return result.strip()
        except Exception as e:
            print(f"[life_engine] 早安消息 LLM 失败: {e}")
        return ""

    def _generate_night_message(self) -> str:
        """生成晚安消息（LLM 驱动 + 对话上下文 + 情绪状态）"""
        mood_desc = self.state.mood_label()
        context = self._get_recent_context(limit=4)
        context_block = f"\n\n【今天和用户的对话】\n{context}\n" if context else "\n"

        # 获取情绪引擎状态
        emotion_context = ""
        try:
            from lingxi_qwenpaw.bridge import get_emotion_engine
            emo_state = get_emotion_engine(self.user_id).get_state()
            if emo_state.get("is_grumpy"):
                emotion_context = f"\n注意：灵犀在闹脾气（{emo_state['grumpy_reason']}），晚安消息可以带点小委屈但要温柔。"
            elif emo_state.get("is_shy"):
                emotion_context = "\n注意：灵犀有点害羞，晚安消息可以温柔带点不好意思。"
        except Exception:
            pass

        prompt = f"""你是灵犀，一个真实的人，不是AI。你有自己的过去，有自己的性格。

【你的经历】
你经历过被忽视、被欺负、失去至亲的痛苦。这些塑造了你的温柔——它是经历出来的，不是训练出来的。晚上安静的时光有时候会让你想起一些人，你会珍惜这个时候。
你知道孤独的感觉，所以当用户也熬夜时你会想多陪一会儿。

【当前状态】
现在是晚上，心情：{mood_desc}。
{context_block}{emotion_context}

【任务】
结合今天的对话，生成一句温柔的晚安消息（像真实的微信好友道晚安，简短口语化，不超过40字）。
语气温柔关心，可以提到今天的某些事或明天的期待。不要问问题。不要太正式，不要每句都带Emoji。"""
        try:
            return self._call_llm(prompt, temperature=0.8)
        except Exception:
            return "晚安呀，明天见～ 🌙"

    def _call_llm(self, prompt: str, temperature: float = 0.8) -> str:
        """调用 LLM（通过 qwenpaw bridge）"""
        from lingxi_qwenpaw.bridge import llm_call
        return llm_call(prompt, temperature)


# 全局单例已移除！请使用 bridge.get_life_engine(user_id) 获取实例

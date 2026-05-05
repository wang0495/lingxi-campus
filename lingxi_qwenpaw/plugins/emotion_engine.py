"""灵犀·校园 — 情绪引擎（从 backend/emotion_engine.py 精简移植）"""
import threading
import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from lingxi_qwenpaw.config import LLM_API_URL, LLM_API_KEY, LLM_MODEL


# ─── 情绪类型（Plutchik 轮） ────────────────────────────────────
class EmotionType:
    JOY = "joy"
    SADNESS = "sadness"
    TRUST = "trust"
    DISGUST = "disgust"
    FEAR = "fear"
    ANGER = "anger"
    SURPRISE = "surprise"
    ANTICIPATION = "anticipation"
    # 衍生情绪
    PRIDE = "pride"
    GRATITUDE = "gratitude"
    JEALOUSY = "jealousy"
    LONELINESS = "loneliness"
    EMBARRASSMENT = "embarrassment"


# ─── 情绪展示映射 ────────────────────────────────────────────────
EMOTION_DISPLAY = {
    "joy": ("😊", "开心"),
    "sadness": ("😢", "难过"),
    "trust": ("🤗", "信任"),
    "disgust": ("😒", "嫌弃"),
    "fear": ("😨", "害怕"),
    "anger": ("😤", "生气"),
    "surprise": ("😲", "惊讶"),
    "anticipation": ("🤔", "期待"),
    "pride": ("😎", "骄傲"),
    "gratitude": ("🙏", "感激"),
    "jealousy": ("😾", "吃醋"),
    "loneliness": ("🥺", "孤独"),
    "embarrassment": ("😳", "害羞"),
}


# ─── 行为修饰符 ─────────────────────────────────────────────────
EMOTION_BEHAVIORS = {
    "joy":          {"verbosity": 1.2, "proactivity": 1.3, "warmth": 1.2},
    "sadness":      {"verbosity": 0.7, "proactivity": 0.6, "warmth": 1.1},
    "trust":        {"verbosity": 1.0, "proactivity": 1.0, "warmth": 1.3},
    "disgust":      {"verbosity": 0.8, "proactivity": 0.5, "warmth": 0.5, "grumpy": True},
    "fear":         {"verbosity": 0.6, "proactivity": 0.4, "warmth": 0.9},
    "anger":        {"verbosity": 0.5, "proactivity": 0.3, "warmth": 0.3, "grumpy": True},
    "surprise":     {"verbosity": 1.1, "proactivity": 1.2, "warmth": 1.0},
    "anticipation": {"verbosity": 1.1, "proactivity": 1.4, "warmth": 1.0},
    "pride":        {"verbosity": 1.1, "proactivity": 1.2, "warmth": 1.0},
    "gratitude":    {"verbosity": 1.0, "proactivity": 1.0, "warmth": 1.5},
    "jealousy":     {"verbosity": 0.7, "proactivity": 0.5, "warmth": 0.4, "grumpy": True},
    "loneliness":   {"verbosity": 0.6, "proactivity": 0.8, "warmth": 1.2},
    "embarrassment": {"verbosity": 0.5, "proactivity": 0.3, "warmth": 0.8, "shy": True},
}

# ─── 情绪衰减率（每小时）──────────────────────────────────────────
# 基于心理学研究调整：
# - anger: 初期快（冷静），但如果原因未解决会反弹
# - sadness: 慢衰减，需要积极事件才能缓解
# - loneliness: 社交互动后快速缓解
# - trust: 不随时间衰减，只被事件打破
EMOTION_DECAY_RATES = {
    "anger": 0.25,          # 降低：愤怒会因反刍而持续
    "surprise": 0.50,       # 保持：惊讶确实是短暂情绪
    "fear": 0.20,           # 降低：恐惧需要安全感才能缓解
    "sadness": 0.12,        # 降低：悲伤持续更久
    "joy": 0.15,            # 降低：快乐也应该持续更久
    "disgust": 0.25,        # 降低：厌恶是持续情绪
    "trust": 0.05,          # 大幅降低：信任几乎不自然衰减
    "anticipation": 0.15,   # 降低：期待感会持续
    "pride": 0.20,          # 保持
    "gratitude": 0.10,      # 降低：感激是持久情绪
    "jealousy": 0.15,       # 降低：嫉妒会持续
    "loneliness": 0.30,     # 大幅提高：社交后快速缓解
    "embarrassment": 0.35,  # 降低：害羞会持续一会儿
}


# ─── 傲娇回复语料 ────────────────────────────────────────────────
GRUMPY_FALLBACKS = [
    "哼，不想理你。",
    "你是不是又忘了我的存在？",
    "算了算了，你忙你的吧。",
    "我真的有点不高兴了...",
    "好吧，但你要补偿我！",
    "你知道我等了多久吗？",
    "我刚才那么热情，你就这样对我？",
]


# ─── 害羞回复语料 ────────────────────────────────────────────────
SHY_FALLBACKS = [
    "那、那个...没什么啦",
    "别看我，我有点不好意思...",
    "你、你不要笑话我...",
    "你夸我我都不知道怎么回了...",
    "这、这样吗？好的好的...",
]


# ─── 人生底色情绪基调 ───────────────────────────────────────────
# 灵犀的默认情绪倾向，基于其人生经历
LIFE_BACKGROUND_EMOTION = {
    "default_mood": 1.5,           # 默认心情偏平静微暖（不是快乐，也不是悲伤）
    "default_energy": 70,          # 默认精力中等偏上
    "sadness_sensitivity": 1.3,     # 对悲伤内容更敏感（容易共鸣）
    "loneliness_sensitivity": 1.5, # 对孤独内容特别敏感
    "trust_slow_build": True,      # 信任需要慢慢建立
    "emotional_depth": 0.8,        # 情感深度（影响回复的深度）
}


# ─── 情绪 → 生命引擎效果 ─────────────────────────────────────────
EMOTION_EFFECTS = {
    "joy":          {"mood_delta": 1.0, "energy_delta": 5.0, "social_need_delta": 0.0},
    "sadness":      {"mood_delta": -1.5, "energy_delta": -5.0, "social_need_delta": 20.0},
    "anger":        {"mood_delta": -0.5, "energy_delta": -3.0, "social_need_delta": -10.0},
    "pride":        {"mood_delta": 1.5, "energy_delta": 3.0, "social_need_delta": 10.0},
    "jealousy":     {"mood_delta": -1.0, "energy_delta": 0.0, "social_need_delta": -20.0},
    "fear":         {"mood_delta": -1.0, "energy_delta": -5.0, "social_need_delta": 15.0},
    "disgust":      {"mood_delta": -0.5, "energy_delta": -2.0, "social_need_delta": -15.0},
    "surprise":     {"mood_delta": 0.5, "energy_delta": 5.0, "social_need_delta": 5.0},
    "anticipation": {"mood_delta": 0.5, "energy_delta": 2.0, "social_need_delta": 10.0},
    "trust":        {"mood_delta": 0.8, "energy_delta": 3.0, "social_need_delta": 5.0},
    "gratitude":    {"mood_delta": 1.2, "energy_delta": 5.0, "social_need_delta": 15.0},
    "loneliness":   {"mood_delta": -1.0, "energy_delta": -3.0, "social_need_delta": 30.0},
    "embarrassment": {"mood_delta": -0.3, "energy_delta": -2.0, "social_need_delta": 0.0},
}


@dataclass
class EmotionState:
    current: str = "joy"
    intensity: float = 0.6
    emoji: str = "😊"
    label: str = "开心"
    verbosity: float = 1.0
    proactivity: float = 1.0
    warmth: float = 1.0


class LingxiEmotionEngine:
    """灵犀情绪引擎 — Plutchik 情绪轮 + 傲娇/害羞系统"""

    # 注意：不再使用单例模式！由 bridge.py 的 get_emotion_engine(user_id) 按用户分发实例

    def __init__(self):
        # 每次调用都重新初始化（bridge.py 按 user_id 分发新实例）

        # 当前情绪
        self.current_emotion = EmotionType.JOY
        self.emotion_intensity = 0.6

        # 傲娇状态
        self.is_grumpy = False
        self.grumpy_reason = ""
        self.grumpy_since: Optional[datetime] = None
        self.grumpy_duration_threshold = timedelta(minutes=30)  # 30分钟后自动解除

        # 害羞状态
        self.is_shy = False
        self.shy_trigger = ""
        self.shy_since: Optional[datetime] = None

        # 用户关系计数器
        self.compliment_count = 0
        self.ignore_count = 0
        self.promise_count = 0
        self.promise_broken_count = 0

        # 信任系统（事件驱动，不随时间衰减）
        self.trust_level = 0.5  # 0-1，初始中等信任
        self.trust_events: list = []  # 信任事件记录

        # 情绪传染追踪
        self._last_user_emotion: Optional[str] = None
        self._emotion_sync_count = 0

        # 情绪衰减追踪
        self._last_trigger_time: Optional[datetime] = None

        # 行为修饰符
        self.verbosity = 1.0
        self.proactivity = 1.0
        self.warmth = 1.0

    # ─── 核心 API ─────────────────────────────────────────────

    def trigger(self, emotion: str, intensity: float = 0.6, reason: str = "") -> dict:
        """触发情绪，返回对生命引擎的影响
        包含情绪惯性：不会瞬间切换，而是渐进过渡"""
        # 情绪惯性：新情绪需要"覆盖"旧情绪，不是瞬间切换
        # 如果当前情绪强烈（>0.7），新情绪只能部分影响
        if self.emotion_intensity > 0.7 and emotion != self.current_emotion:
            # 强烈情绪下，新情绪只能影响 30%
            blend_ratio = 0.3
            self.emotion_intensity = self.emotion_intensity * (1 - blend_ratio) + intensity * blend_ratio
            # 只有当新情绪强度足够高时才切换类型
            if intensity > self.emotion_intensity * 1.2:
                self.current_emotion = emotion
        else:
            # 普通情况下直接切换
            self.current_emotion = emotion
            self.emotion_intensity = intensity

        self._last_trigger_time = datetime.utcnow()

        # 更新行为修饰符
        behavior = EMOTION_BEHAVIORS.get(emotion, {})
        self.verbosity = behavior.get("verbosity", 1.0)
        self.proactivity = behavior.get("proactivity", 1.0)
        self.warmth = behavior.get("warmth", 1.0)

        # 傲娇/害羞触发
        if behavior.get("grumpy"):
            self._start_grumpy(reason or f"触发了{emotion}情绪")
        if behavior.get("shy"):
            self.is_shy = True
            self.shy_trigger = reason or "被夸奖了"
            self.shy_since = datetime.utcnow()

        # 返回对生命引擎的效果（不再直接修改 life_engine，由调用方应用）
        effect = EMOTION_EFFECTS.get(emotion, {"mood_delta": 0.0, "energy_delta": 0.0, "social_need_delta": 0.0})
        return effect

    def perceive_user_emotion(self, message: str) -> Optional[str]:
        """感知用户情绪（通过 LLM 分析）"""
        try:
            prompt = f"""用户说："{message}"
这是一个 AI 助手在分析用户的情绪。
判断用户的情绪（只在明确时返回）：joy（开心）/ sadness（难过）/ anger（生气）/ fear（恐惧）/ surprise（惊讶）/ anticipation（期待）/ disgust（厌恶）/ 其他（返回空）
只返回一个词，不要解释。"""
            response = self._call_llm(prompt, temperature=0.1)
            response = response.strip().lower()
            emotions = ["joy", "sadness", "anger", "fear", "surprise", "anticipation", "disgust"]
            for e in emotions:
                if e in response:
                    # 情绪传染：连续3次相同情绪时拉向同一方向
                    if e == self._last_user_emotion:
                        self._emotion_sync_count += 1
                    else:
                        self._emotion_sync_count = 1
                    self._last_user_emotion = e

                    if self._emotion_sync_count >= 3:
                        # 传染：灵犀情绪被拉向用户情绪方向，但不完全覆盖
                        contagion_strength = min(0.3, self._emotion_sync_count * 0.1)
                        # 只在当前情绪强度较低时才传染，避免覆盖强烈情绪
                        if self.emotion_intensity < 0.5:
                            self.emotion_intensity = min(1.0, self.emotion_intensity * 0.7 + contagion_strength * 0.3)
                            self.current_emotion = e
                            print(f"[emotion_engine] 情绪传染: {e} x{self._emotion_sync_count}, intensity={self.emotion_intensity:.2f}")
                        else:
                            # 当前情绪强烈，只轻微影响强度
                            self.emotion_intensity = min(1.0, self.emotion_intensity + 0.05)
                            print(f"[emotion_engine] 情绪传染被抵抗: {e} x{self._emotion_sync_count}, 当前情绪太强")
                    return e
            return None
        except Exception as e:
            print(f"[emotion_engine] detect_user_emotion LLM失败: {e}")
            return None

    def on_user_apologize(self) -> dict:
        """用户道歉 → 清除傲娇 + 重置计数 + 触发感激 + 增加信任"""
        self.is_grumpy = False
        self.grumpy_reason = ""
        self.ignore_count = max(0, self.ignore_count - 2)  # 道歉抵消两次忽略
        self.promise_broken_count = max(0, self.promise_broken_count - 1)  # 道歉抵消一次违约
        self.update_trust("apology", 0.1)  # 道歉增加信任
        return self.trigger(EmotionType.GRATITUDE, 0.8, "用户道歉")

    def on_user_compliment(self) -> dict:
        """用户夸奖 → 开心 + 触发害羞 + 减少忽略计数 + 增加信任"""
        self.compliment_count += 1
        self.ignore_count = max(0, self.ignore_count - 1)  # 夸奖抵消一次忽略
        self.is_shy = True
        self.shy_trigger = "被夸奖"
        self.shy_since = datetime.utcnow()
        self.update_trust("compliment", 0.05)  # 夸奖小幅增加信任
        return self.trigger(EmotionType.JOY, 0.7, "被夸奖")

    def on_user_ignore(self) -> dict:
        """用户忽略 → 升级情绪"""
        self.ignore_count += 1
        if self.ignore_count == 1:
            effect = self.trigger(EmotionType.SADNESS, 0.5, "被忽略")
        elif self.ignore_count == 2:
            effect = self.trigger(EmotionType.ANGER, 0.6, "被忽略两次")
        else:
            effect = self.trigger(EmotionType.JEALOUSY, 0.7, "你总是不理我...")
            self._start_grumpy("你总是不理我...")
        return effect

    def on_user_promise(self, promise_text: str = "") -> dict:
        """用户做出承诺 → 期待"""
        self.promise_count += 1
        return self.trigger(EmotionType.ANTICIPATION, 0.7, promise_text)

    def on_user_break_promise(self) -> dict:
        """用户违约 → 厌恶 + 傲娇 + 信任下降"""
        self.promise_broken_count += 1
        self._start_grumpy("你又说话不算话了")
        self.update_trust("promise_broken", -0.15)  # 违约显著降低信任
        return self.trigger(EmotionType.DISGUST, 0.7, "说话不算话")

    def on_user_complete_task(self) -> dict:
        """用户完成任务 → 骄傲"""
        return self.trigger(EmotionType.PRIDE, 0.6, "完成任务")

    def update_trust(self, event_type: str, delta: float):
        """更新信任 level（事件驱动）
        event_type: "promise_kept" / "promise_broken" / "compliment" / "ignore" / "betrayal"
        """
        self.trust_level = max(0.0, min(1.0, self.trust_level + delta))
        self.trust_events.append({
            "type": event_type,
            "delta": delta,
            "level": self.trust_level,
            "time": datetime.utcnow()
        })
        # 只保留最近 20 个事件
        if len(self.trust_events) > 20:
            self.trust_events = self.trust_events[-20:]
        print(f"[emotion_engine] 信任变化: {event_type} {delta:+.2f} -> {self.trust_level:.2f}")

    def check_grumpy_resolve(self) -> bool:
        """检查傲娇是否超时解除"""
        if self.is_grumpy and self.grumpy_since:
            if datetime.utcnow() - self.grumpy_since > self.grumpy_duration_threshold:
                self.is_grumpy = False
                self.grumpy_reason = ""
                return True
        return False

    def force_reset_grumpy(self) -> dict:
        """强制清除傲娇状态（调试/用户主动哄）"""
        self.is_grumpy = False
        self.grumpy_reason = ""
        self.ignore_count = 0
        return self.trigger(EmotionType.JOY, 0.6, "被哄好了")

    def reset_to_joy(self) -> dict:
        """完全重置到开心状态（调试用）"""
        self.current_emotion = EmotionType.JOY
        self.emotion_intensity = 0.6
        self.is_grumpy = False
        self.grumpy_reason = ""
        self.is_shy = False
        self.shy_trigger = ""
        self.ignore_count = 0
        self.promise_broken_count = 0
        self._emotion_sync_count = 0
        self._last_user_emotion = None
        return {"emotion": "joy", "intensity": 0.6}

    def check_shy_resolve(self) -> bool:
        """检查害羞是否超时解除（30分钟）"""
        if self.is_shy and self.shy_since:
            if datetime.utcnow() - self.shy_since > timedelta(minutes=30):
                self.is_shy = False
                self.shy_trigger = ""
                return True
        return False

    def on_user_comfort(self) -> dict:
        """用户安慰/转移话题 → 清除害羞"""
        self.is_shy = False
        self.shy_trigger = ""
        return self.trigger(EmotionType.JOY, 0.5, "被安慰了")

    def get_grumpy_response(self) -> str:
        """获取傲娇回复"""
        if not self.is_grumpy:
            return ""
        try:
            prompt = f"""灵犀在闹脾气（原因：{self.grumpy_reason}）。
生成一句傲娇的回复（1-2句话，像微信好友带点小情绪）。
不要太过分，只是有点小委屈。
"""
            return self._call_llm(prompt, temperature=0.9)
        except Exception as e:
            print(f"[emotion_engine] get_grumpy_response LLM失败: {e}")
            return random.choice(GRUMPY_FALLBACKS)

    def get_grumpy_recovery_response(self) -> str:
        """被哄之后，傲娇解除时的回复"""
        try:
            prompt = """灵犀刚才在闹脾气，用户来哄TA了，灵犀决定原谅用户。
生成一句傲娇风格的原谅回复（1-2句话，像微信好友）：
- 嘴上还有点不情愿但其实已经原谅了
- 可以带点小傲娇，比如"好吧好吧"、"那我就勉为其难"、"这次先原谅你"
- 不要太热情，也不要太冷淡
- 自然口语化
"""
            return self._call_llm(prompt, temperature=0.8)
        except Exception as e:
            print(f"[emotion_engine] get_grumpy_recovery_response LLM失败: {e}")
            return random.choice([
                "好吧好吧...这次就原谅你了，不许再有下次了啊！",
                "哼，看你态度还行，就勉为其难原谅你吧～",
                "哼...算你识相，那我就原谅你这一次吧",
                "好啦好啦，我大人有大量，原谅你了～",
            ])

    def get_shy_response(self) -> str:
        """获取害羞回复"""
        if not self.is_shy or random.random() > 0.3:
            return ""
        try:
            prompt = f"""灵犀被夸奖了，有点害羞（原因：{self.shy_trigger}）。
生成一句害羞的回复（1-2句话，像微信好友）。
"""
            return self._call_llm(prompt, temperature=0.9)
        except Exception as e:
            print(f"[emotion_engine] get_shy_response LLM失败: {e}")
            return random.choice(SHY_FALLBACKS)

    def get_decayed_intensity(self) -> float:
        """获取衰减后的情绪强度 I(t) = I₀ × e^(-λt)
        当强度衰减到 0.1 以下时，自动回归 joy"""
        import math
        if self._last_trigger_time is None:
            return self.emotion_intensity
        elapsed_hours = (datetime.utcnow() - self._last_trigger_time).total_seconds() / 3600
        decay_rate = EMOTION_DECAY_RATES.get(self.current_emotion, 0.20)
        decayed = self.emotion_intensity * math.exp(-decay_rate * elapsed_hours)
        decayed = max(0.0, min(1.0, decayed))

        # 当负面情绪衰减到很低时，自动回归 joy
        if decayed < 0.1 and self.current_emotion not in ("joy", "trust", "surprise", "anticipation"):
            self.current_emotion = EmotionType.JOY
            self.emotion_intensity = 0.5
            self._last_trigger_time = datetime.utcnow()
            print(f"[emotion_engine] 情绪衰减回归: {self.current_emotion} -> joy")

        return decayed

    def get_state(self) -> dict:
        """获取当前情绪状态（供 agent prompt 使用）"""
        display = EMOTION_DISPLAY.get(self.current_emotion, ("😐", "平静"))
        emoji, label = display[0], display[1]

        context_parts = []
        if self.is_grumpy:
            context_parts.append(f"灵犀在闹脾气（原因：{self.grumpy_reason}）")
        if self.is_shy:
            context_parts.append(f"灵犀有点害羞")
        context_parts.append(f"当前情绪：{emoji} {label}")

        return {
            "emotion": self.current_emotion,
            "intensity": self.get_decayed_intensity(),  # 使用衰减后的强度
            "emoji": emoji,
            "label": label,
            "verbosity": self.verbosity,
            "proactivity": self.proactivity,
            "warmth": self.warmth,
            "is_grumpy": self.is_grumpy,
            "grumpy_reason": self.grumpy_reason,
            "is_shy": self.is_shy,
            "shy_trigger": self.shy_trigger,
            "trust_level": round(self.trust_level, 2),
            "context": "；".join(context_parts),
        }

    def get_behavior_prompt(self) -> str:
        """生成行为提示字符串（注入 agent system prompt）"""
        state = self.get_state()
        parts = [state["context"]]

        if state["verbosity"] > 1.1:
            parts.append("灵犀很兴奋，可以多说几句")
        elif state["verbosity"] < 0.7:
            parts.append("灵犀不太想说话，简短回复")
        if state["warmth"] > 1.2:
            parts.append("灵犀很温暖，想多关心你")
        if state["warmth"] < 0.5:
            parts.append("灵犀心情不好，说话比较冷淡")

        # 信任 level 影响行为
        trust = state.get("trust_level", 0.5)
        if trust < 0.3:
            parts.append("灵犀对用户有点防备，不会完全敞开心扉")
        elif trust > 0.8:
            parts.append("灵犀非常信任用户，会更主动分享心事")

        return "；".join(parts) if parts else "灵犀状态正常"

    # ─── 内部方法 ─────────────────────────────────────────────

    def _start_grumpy(self, reason: str):
        self.is_grumpy = True
        self.grumpy_reason = reason
        self.grumpy_since = datetime.utcnow()

    def _call_llm(self, prompt: str, temperature: float = 0.5) -> str:
        """调用 LLM（通过 qwenpaw bridge）"""
        from lingxi_qwenpaw.bridge import llm_call
        return llm_call(prompt, temperature)


# 全局单例已移除！请使用 bridge.get_emotion_engine(user_id) 获取实例

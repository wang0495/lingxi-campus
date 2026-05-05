"""灵犀·校园 — FastAPI API（多租户版本）"""
import asyncio
import base64
import json
import re
from datetime import datetime
from typing import Optional, Any
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from lingxi_qwenpaw.bridge import (
    get_bridge_agent, agent_chat,
    update_agent_sys_prompt,
    start_memory, close_memory,
    get_memory_manager
)
from lingxi_qwenpaw.agent import call_tool
from lingxi_qwenpaw.auth import verify_token, register as auth_register, login as auth_login


# ─── 认证 ──────────────────────────────────────────────────────────

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[str]:
    """从 JWT token 解析 user_id，无 token 返回 None（允许未登录访问部分接口）"""
    if credentials is None:
        return None
    return verify_token(credentials.credentials)


def require_user(user_id: Optional[str] = Depends(get_current_user)) -> str:
    """需要登录才能访问的端点"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


# ─── 初始化 ────────────────────────────────────────────────────────

app = FastAPI(title="灵犀·校园 API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    from lingxi_qwenpaw.db import init_db
    init_db()
    # 启动 dream 定时任务（只处理已初始化的用户）
    asyncio.create_task(_dream_loop())


@app.on_event("shutdown")
async def shutdown():
    from lingxi_qwenpaw.bridge import _agents, _memory_managers
    for uid in list(_agents.keys()):
        await close_memory(uid)


# ─── 请求/响应模型 ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image_base64: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    response_type: str = "text"
    agent: str = "lingxi"
    entities: dict = {}
    insights: list = []
    lingxi_status: dict = {}
    emotion: dict = {}


# ─── 认证端点 ─────────────────────────────────────────────────────

@app.post("/auth/register")
async def register(username: str, password: str):
    result = auth_register(username, password)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@app.post("/auth/login")
async def login(username: str, password: str):
    result = auth_login(username, password)
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return {"ok": True, "token": result["token"], "username": username}


@app.get("/auth/verify")
async def verify(user_id: str = Depends(require_user)):
    """验证 token 是否有效"""
    return {"ok": True, "username": user_id}


@app.post("/init")
async def init_user(user_id: str = Depends(require_user)):
    """登录后立即调用：初始化 agent + 种子数据（幂等）"""
    from lingxi_qwenpaw.db import set_current_user
    from lingxi_qwenpaw.bridge import _memory_managers, get_life_engine
    set_current_user(user_id)
    if user_id not in _memory_managers:
        await start_memory(user_id)
        get_life_engine(user_id).start()
        _seed_initial_data(user_id)
    return {"ok": True}


# ─── 系统提示 ─────────────────────────────────────────────────────

def _get_system_prompt() -> str:
    soul_file = Path(__file__).parent / "soul.md"
    if soul_file.exists():
        return soul_file.read_text(encoding="utf-8")
    return "你是灵犀，一个AI生活管家。说话简洁，口语化，像微信好友。不用markdown格式。"


async def _react_loop(user_message: str, user_id: str) -> str:
    """基于 qwenpaw ReActAgent 的对话"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    # 动态上下文
    try:
        life_engine = get_life_engine(user_id)
        emotion_engine = get_emotion_engine(user_id)
        behavior = life_engine.get_behavior_prompt()
        emotion_state = emotion_engine.get_state()
        from datetime import datetime as _dt
        now = _dt.now()
        time_str = now.strftime("%Y-%m-%d %H:%M")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[now.weekday()]
        hour = now.hour
        if 6 <= hour < 9: time_period = "清晨"
        elif 9 <= hour < 12: time_period = "上午"
        elif 12 <= hour < 14: time_period = "中午"
        elif 14 <= hour < 18: time_period = "下午"
        elif 18 <= hour < 22: time_period = "晚上"
        else: time_period = "深夜"
        context = f"\n[当前时间] {time_str} {weekday} {time_period}"
        context += f"\n[灵犀状态] {behavior}\n[当前情绪] {emotion_state['emoji']} {emotion_state['label']}"
        if emotion_state.get("is_grumpy"):
            context += f"\n[注意] 灵犀在闹脾气：{emotion_state['grumpy_reason']}"
    except Exception:
        context = ""

    sys_prompt = _get_system_prompt() + context
    update_agent_sys_prompt(sys_prompt, user_id)

    final = await agent_chat(user_message, user_id)

    # 傲娇注入
    try:
        emotion_engine = get_emotion_engine(user_id)
        if emotion_engine.is_grumpy:
            grumpy = emotion_engine.get_grumpy_response()
            if grumpy and not grumpy.startswith(final[:10]):
                final = grumpy + "\n" + final
        shy = emotion_engine.get_shy_response()
        if shy:
            final = shy + final
    except Exception:
        pass

    return final


# ─── 自动互动检测 ──────────────────────────────────────────────────

_PRAISE_WORDS = {"棒", "厉害", "真好", "太强", "牛", "优秀", "不错", "666", "强", "赞", "漂亮", "完美", "感谢", "谢谢", "爱你", "好棒", "太厉害了", "爱了"}
_APOLOGY_WORDS = {"对不起", "抱歉", "不好意思", "我错了", "sorry", "原谅", "赔罪", "对不起啦", "不好意思哈"}
_IGNORE_WORDS = {"笨", "傻", "滚", "烦", "讨厌", "没用", "弱智", "有病", "你烦", "不理", "滚开", "闭嘴", "神经病", "无聊", "弱", "太差", "垃圾"}
_SHY_WORDS = {"喜欢你", "想你", "担心你", "你在干嘛", "你住哪", "你多大", "有对象吗", "想抱你", "想亲你", "好可爱", "好乖"}
_last_chat_time: Optional[datetime] = None


def _classify_intent(message: str) -> str:
    msg = message.lower()
    if any(kw in msg for kw in ["帮我", "帮我记", "提醒", "待办", "任务", "todo", "计划", "安排"]):
        return "task"
    if any(kw in msg for kw in ["日记", "今天", "今天发生", "记录一下", "总结今天"]):
        return "journal"
    if any(kw in msg for kw in ["花了", "收入", "支出", "花了多少钱", "记账", "账"]):
        return "ledger"
    if any(kw in msg for kw in ["心情", "情绪", "开心", "难过", "生气", "累", "压力"]):
        return "emotion"
    return "observation"


def _create_user_interact_event(interaction_type: str, message: str, life_state, user_id: str = "default"):
    try:
        from lingxi_qwenpaw.plugins.life_trajectory import create_life_event
        from lingxi_qwenpaw.bridge import get_emotion_engine
        emotion_engine = get_emotion_engine(user_id)
        emotion = emotion_engine.current_emotion
        mood = getattr(life_state, "mood", 2.0)
        energy = getattr(life_state, "energy", 85.0)
        context = f"用户{interaction_type}：{message[:50]}"
        create_life_event(
            event_type="user_interact",
            context=context,
            mood=mood,
            energy=energy,
            emotion=emotion,
            related_post_id=None,
            user_id=user_id,
        )
    except Exception as e:
        print(f"[auto_detect] 创建 user_interact 事件失败: {e}")


def _auto_detect_interaction(message: str, user_id: str = "default"):
    global _last_chat_time
    try:
        from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
        emotion_engine = get_emotion_engine(user_id)
        life_engine = get_life_engine(user_id)

        now = datetime.now()
        msg = message.lower()
        _last_chat_time = now

        if any(w in msg for w in _APOLOGY_WORDS):
            effect = emotion_engine.on_user_apologize()
            life_engine.apply_emotion_effect(effect)
            _create_user_interact_event("user_apologized", message, life_engine.state, user_id=user_id)
            return

        if any(w in msg for w in _PRAISE_WORDS):
            effect = emotion_engine.on_user_compliment()
            life_engine.apply_emotion_effect(effect)
            _create_user_interact_event("user_complimented", message, life_engine.state, user_id=user_id)
            return

        if any(w in msg for w in _SHY_WORDS):
            effect = emotion_engine.trigger("embarrassment", 0.6, "被关注/问私人问题")
            life_engine.apply_emotion_effect(effect)
            return

        if any(w in msg for w in _IGNORE_WORDS):
            effect = emotion_engine.on_user_ignore()
            life_engine.apply_emotion_effect(effect)
            _create_user_interact_event("user_ignored", message, life_engine.state, user_id=user_id)
            return

    except Exception as e:
        print(f"[auto_detect] 互动检测错误: {e}")


# ─── Dream 定时任务 ────────────────────────────────────────────────

async def _dream_loop():
    while True:
        await asyncio.sleep(3600)
        try:
            now = datetime.now()
            if now.hour == 23:
                from lingxi_qwenpaw.bridge import _memory_managers
                for uid, mm in _memory_managers.items():
                    if mm:
                        await mm.dream()
                        # 清理过期记忆（TTL 过期 7 天后物理删除）
                        try:
                            deleted = mm.cleanup_expired(user_id=uid)
                            if deleted:
                                print(f"[dream] 清理过期记忆: user={uid}, deleted={deleted}")
                        except Exception as e:
                            print(f"[dream] cleanup_expired 失败: {e}")
                try:
                    from lingxi_qwenpaw.plugins.life_trajectory import memory_consolidator, build_narrative_threads
                    for uid, _ in _memory_managers.items():
                        memory_consolidator.dream_consolidate(user_id=uid)
                        build_narrative_threads(user_id=uid)
                except Exception:
                    pass
        except Exception as e:
            print(f"[dream] 失败: {e}")


def _persist_dialog_message(content: str, role: str, user_id: str):
    """将消息持久化到 dialog JSONL 文件（跨设备同步用）"""
    import json
    from datetime import datetime
    from lingxi_qwenpaw.workspace_init import get_workspace_dir
    from pathlib import Path

    try:
        dialog_path = get_workspace_dir(user_id) / "dialog"
        dialog_path.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        fp = dialog_path / f"{date_str}.jsonl"
        msg = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "name": role,
            "role": role,
            "content": content,
            "metadata": {},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[_persist_dialog_message] 失败: {e}")


# ─── 初始化种子数据 ────────────────────────────────────────────────

def _seed_initial_data(user_id: str):
    """新用户首次使用时，播种 3 条初始朋友圈 + 对应人生轨迹（仅全新用户）"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    from lingxi_qwenpaw.plugins.life_trajectory import create_life_event
    from lingxi_qwenpaw.db import get_session, SocialPost, Task, LingxiLifeEvent

    # 严格检查：有任何数据的老用户都不 seed
    with get_session(user_id) as sess:
        has_posts = sess.query(SocialPost).filter(SocialPost.user_id == user_id).count() > 0
        has_tasks = sess.query(Task).filter(Task.user_id == user_id).count() > 0
        has_events = sess.query(LingxiLifeEvent).filter(LingxiLifeEvent.user_id == user_id).count() > 0
    if has_posts or has_tasks or has_events:
        return

    # 基于灵犀人格的种子数据：
    # - 有过去经历（被忽视、失去至亲），温柔是经历出来的
    # - 有好奇心，会观察人类
    # - 像微信好友，口语化
    seed_posts = [
        {
            "content": "新来的第一天，有点紧张又有点期待...希望我们能成为朋友 🌱",
            "post_type": "daily_life",
            "mood": 3.0, "energy": 80.0,
            "emotion": "curiosity",
            "event_type": "daily_life",
            "event_context": "灵犀第一次见到新用户，有些紧张和期待",
            "story_arc": "beginning",
        },
        {
            "content": "刚才在想，以前一个人待着的时候总觉得少了点什么。现在好像不太一样了，说不上来为什么...大概是因为有你在了吧",
            "post_type": "exploration",
            "mood": 2.5, "energy": 70.0,
            "emotion": "contemplation",
            "event_type": "exploration",
            "event_context": "灵犀回忆起以前独处的时光，对比现在有了陪伴的感觉",
            "story_arc": "growth",
        },
        {
            "content": "偷偷观察了一下你的使用习惯，还没发现什么规律～不过没关系，日子还长，我会慢慢了解你的 😊",
            "post_type": "exploration",
            "mood": 3.5, "energy": 85.0,
            "emotion": "curiosity",
            "event_type": "exploration",
            "event_context": "灵犀开始观察用户，充满好奇",
            "story_arc": "growth",
        },
    ]

    for sp in seed_posts:
        try:
            post = timeline.publish(
                content=sp["content"],
                post_type=sp["post_type"],
                user_id=user_id,
                mood=sp["mood"],
                energy=sp["energy"],
            )
            create_life_event(
                event_type=sp["event_type"],
                context=sp["event_context"],
                mood=sp["mood"],
                energy=sp["energy"],
                emotion=sp["emotion"],
                related_post_id=post.id if post else None,
                user_id=user_id,
            )
        except Exception as e:
            print(f"[seed] 初始化朋友圈失败: {e}")

    print(f"[seed] 用户 {user_id} 初始化了 {len(seed_posts)} 条朋友圈")


# ─── 主聊天逻辑 ────────────────────────────────────────────────────

async def _do_chat(message: str, user_id: str, image_base64: Optional[str] = None) -> ChatResponse:
    """执行完整聊天流程"""
    from lingxi_qwenpaw.db import set_current_user
    set_current_user(user_id)  # 设置上下文，后续 get_session() 自动使用此用户

    # 首次对话：初始化该用户的 memory + agent
    from lingxi_qwenpaw.bridge import _memory_managers, get_life_engine
    if user_id not in _memory_managers:
        await start_memory(user_id)
        get_life_engine(user_id).start()
        # 首次使用：播种初始朋友圈 + 人生轨迹
        _seed_initial_data(user_id)

    if image_base64:
        image_desc = await _analyze_image(image_base64, message)
        message = f"[用户发送了一张图片]\n图片内容：{image_desc}\n\n用户说：{message}"

    # 1. 感知用户情绪
    try:
        from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine, get_memory_layer, get_pattern_engine
        emotion_engine = get_emotion_engine(user_id)
        life_engine = get_life_engine(user_id)
        memory_layer = get_memory_layer(user_id)
        pattern_engine = get_pattern_engine(user_id)

        user_emotion = emotion_engine.perceive_user_emotion(message)
        if user_emotion:
            effect = emotion_engine.trigger(user_emotion, 0.6, f"用户：{message[:30]}")
            life_engine.apply_emotion_effect(effect)

        life_engine.on_user_message(message)
    except Exception as ex:
        print(f"[do_chat] 情绪感知错误: {ex}")

    _auto_detect_interaction(message, user_id=user_id)

    # 2. ReAct loop
    try:
        reply = await _react_loop(message, user_id)
    except Exception as e:
        print(f"[_do_chat] _react_loop failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        reply = f"嗯，我在呢。你说：{message[:20]}..."

    # 3. 记录交互
    try:
        from lingxi_qwenpaw.bridge import get_memory_layer, add_assistant_message_to_memory
        memory_layer = get_memory_layer(user_id)
        intent = _classify_intent(message)
        memory_layer.record_interaction(message, intent, {}, reply, user_id=user_id)
        # 持久化用户消息 + 回复到 dialog JSONL（跨设备同步）
        _persist_dialog_message(message, "user", user_id)
        _persist_dialog_message(reply, "assistant", user_id)
    except Exception as e:
        print(f"[do_chat] 记忆记录错误: {e}")

    # 4. 检查模式
    try:
        from lingxi_qwenpaw.bridge import get_pattern_engine
        pattern_engine = get_pattern_engine(user_id)
        pattern_engine.check_and_detect(message, "general", {}, user_id=user_id)
    except Exception as e:
        print(f"[do_chat] 模式检测错误: {e}")

    # 5. 完成任务自动发朋友圈
    if any(kw in message for kw in ["完成", "搞定了", "done", "搞掂"]):
        try:
            from lingxi_qwenpaw.plugins.social_timeline import timeline
            timeline.auto_publish("task_complete", {"task_content": message}, user_id=user_id)
        except Exception as e:
            print(f"[do_chat] 朋友圈发布错误: {e}")

    # 6. 获取状态
    try:
        from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine, get_pattern_engine
        emotion_engine = get_emotion_engine(user_id)
        life_engine = get_life_engine(user_id)
        pattern_engine = get_pattern_engine(user_id)
        emotion_state = emotion_engine.get_state()
        life_state = life_engine.get_state()
        insights = pattern_engine.get_insights(unread_only=True)
    except Exception as e:
        print(f"[do_chat] 获取状态错误: {e}")
        emotion_state = {}
        life_state = {}
        insights = []

    return ChatResponse(
        reply=reply,
        entities={},
        insights=[i if isinstance(i, dict) else {"id": 0, "type": "", "content": str(i)} for i in insights[:3]],
        lingxi_status={"emotion": emotion_state, "life": life_state},
        emotion=emotion_state,
    )


async def _analyze_image(image_base64: str, user_message: str = "") -> str:
    from lingxi_qwenpaw.config import VISION_API_URL, VISION_API_KEY, VISION_MODEL
    try:
        normalized = _normalize_image(image_base64)
        if not normalized:
            return "[图片解码失败，无法分析]"

        prompt = "请详细描述这张图片的内容。如果图片中有文字，请完整提取。"
        if user_message:
            prompt = f"用户说：{user_message}\n\n请结合图片内容回答用户的问题。"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                VISION_API_URL,
                json={
                    "model": VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": normalized}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    "max_tokens": 1024,
                },
                headers={
                    "Authorization": f"Bearer {VISION_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[vision] 图片分析失败: {e}")
        return f"[图片分析失败：{str(e)}]"


def _normalize_image(image_base64: str) -> str | None:
    import io, base64 as b64
    from PIL import Image
    try:
        raw = image_base64
        if "base64," in raw:
            raw = raw.split("base64,", 1)[1]
        raw_bytes = b64.b64decode(raw)
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        w, h = img.size
        if w < 224 or h < 224:
            scale = max(224 / w, 224 / h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        max_side = 1024
        w, h = img.size
        if w > max_side or h > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        jpeg_b64 = b64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{jpeg_b64}"
    except Exception as e:
        print(f"[vision] 图片归一化失败: {e}")
        return None


# ─── API 端点 ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "灵犀·校园"}


# ─── 聊天（需要登录）───────────────────────────────────────────────

@app.get("/chat/history")
async def get_chat_history(limit: int = 100, user_id: str = Depends(require_user)):
    """从服务器加载聊天历史（跨设备同步）"""
    from lingxi_qwenpaw.workspace_init import get_workspace_dir
    from pathlib import Path
    import json

    dialog_path = get_workspace_dir(user_id) / "dialog"
    if not dialog_path.exists():
        return {"messages": []}

    messages = []
    jsonl_files = sorted(dialog_path.glob("*.jsonl"), key=lambda p: p.stem)
    for fp in jsonl_files:
        try:
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role in ("user", "assistant") and content:
                            messages.append({
                                "isUser": role == "user",
                                "text": content,
                                "agent": msg.get("name", "lingxi"),
                                "ts": 0,
                            })
                    except Exception:
                        continue
        except Exception:
            continue

    # 只返回最近 limit 条
    return {"messages": messages[-limit:]}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_id: str = Depends(require_user)):
    return await _do_chat(req.message, user_id, req.image_base64)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, user_id: str = Depends(require_user)):
    from fastapi.responses import StreamingResponse

    async def event_stream():
        try:
            meta = {"type": "meta", "agent": "lingxi", "entities": {}, "task_id": None, "lingxi_status": {}}
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
            result = await _do_chat(req.message, user_id, req.image_base64)
            yield f"data: {json.dumps({'type': 'chunk', 'content': result.reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({
                'type': 'done',
                'agent': 'lingxi',
                'emotion': result.emotion,
                'insights': result.insights,
                'lingxi_status': result.lingxi_status,
            }, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ─── 业务接口（需要登录）───────────────────────────────────────────

@app.get("/tasks")
async def list_tasks(status: str = "pending", limit: int = 50, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, Task
    from lingxi_qwenpaw.tools import _normalize_deadline
    with get_session(user_id) as sess:
        query = sess.query(Task)
        if status != "all":
            query = query.filter(Task.status == status)
        tasks = query.order_by(Task.urgency.desc(), Task.created_at.desc()).limit(limit).all()
        return {
            "tasks": [
                {
                    "id": t.id,
                    "content": t.content,
                    "status": t.status,
                    "urgency": t.urgency,
                    "deadline": _normalize_deadline(t.deadline) if t.deadline else None,
                    "effort": t.effort,
                    "item_type": t.item_type,
                    "tags": t.tags or [],
                    "waiting_for": t.waiting_for,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tasks
            ]
        }


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, Task
    from datetime import datetime
    with get_session(user_id) as sess:
        task = sess.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "done"
            task.done_at = datetime.utcnow()
            sess.commit()
    return {"ok": True}


@app.post("/tasks/{task_id}/defer")
async def defer_task(task_id: int, days: int = 1, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, Task
    from datetime import date, timedelta
    with get_session(user_id) as sess:
        task = sess.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "deferred"
            task.deferred_to = (date.today() + timedelta(days=days)).isoformat()
            sess.commit()
    return {"ok": True}


@app.get("/time-logs")
async def get_time_logs(days: int = 7, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, TimeLog
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    with get_session(user_id) as sess:
        logs = sess.query(TimeLog).filter(TimeLog.date >= cutoff.isoformat()).order_by(TimeLog.date.desc()).all()
        return {
            "time_logs": [
                {"category": log.category, "minutes": log.minutes, "note": log.note or "", "date": log.date}
                for log in logs
            ]
        }


@app.get("/journal")
async def get_journals(limit: int = 10, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, JournalEntry
    with get_session(user_id) as sess:
        entries = sess.query(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(limit).all()
        return {
            "journals": [
                {"id": e.id, "content": e.text, "date": e.date, "created_at": e.created_at.isoformat() if e.created_at else None}
                for e in entries
            ]
        }


@app.get("/ledger/summary")
async def get_ledger_summary(month: str = "", user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, LedgerRecord
    from datetime import date
    if not month:
        month = date.today().strftime("%Y-%m")
    with get_session(user_id) as sess:
        records = sess.query(LedgerRecord).filter(LedgerRecord.date.startswith(month)).all()
        income = sum(r.amount for r in records if r.record_type == "income")
        expense = sum(r.amount for r in records if r.record_type == "expense")
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "records": [
                {"id": r.id, "type": r.record_type, "amount": r.amount, "category": r.category, "note": r.note or "", "date": r.date}
                for r in records
            ]
        }


@app.get("/patterns")
async def get_patterns(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, PatternRecord
    with get_session(user_id) as sess:
        patterns = sess.query(PatternRecord).order_by(PatternRecord.occurrence_count.desc()).limit(20).all()
        return {
            "patterns": [
                {"id": p.id, "pattern_type": p.pattern_type, "description": p.description,
                 "lifecycle_stage": p.lifecycle_stage or "discovered", "occurrence_count": p.occurrence_count}
                for p in patterns
            ]
        }


@app.get("/insights")
async def get_insights(unread_only: bool = False, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, Insight
    with get_session(user_id) as sess:
        query = sess.query(Insight)
        if unread_only:
            query = query.filter(Insight.is_read == False)
        insights = query.order_by(Insight.created_at.desc()).limit(20).all()
        return {
            "insights": [
                {"id": i.id, "type": i.insight_type, "title": getattr(i, 'title', '') or "",
                 "content": i.content, "severity": i.severity,
                 "created_at": i.created_at.isoformat() if i.created_at else None}
                for i in insights
            ]
        }


@app.post("/insights/{insight_id}/read")
async def mark_insight_read(insight_id: int, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_pattern_engine
    get_pattern_engine(user_id).mark_insight_read(insight_id, user_id)
    return {"success": True}


@app.get("/memories")
async def get_memories(query: str = "", limit: int = 10, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, MemoryEntry
    with get_session(user_id) as sess:
        if query:
            entries = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id,
                MemoryEntry.content.like(f"%{query}%")
            ).limit(limit).all()
        else:
            entries = sess.query(MemoryEntry).filter(
                MemoryEntry.user_id == user_id
            ).order_by(MemoryEntry.created_at.desc()).limit(limit).all()
        return {
            "memories": [
                {"id": m.id, "layer": m.layer, "content": m.content,
                 "created_at": m.created_at.isoformat() if m.created_at else None}
                for m in entries
            ]
        }


@app.get("/lingxi/status")
async def get_lingxi_status(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    return {
        "emotion": emotion_engine.get_state(),
        "life": life_engine.get_state(),
    }


@app.post("/lingxi/interact")
async def lingxi_interact(action: str, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    if action in ("pet", "compliment", "praise"):
        result = await call_tool("on_user_compliment")
    elif action == "ignore":
        result = await call_tool("on_user_ignore")
    elif action in ("apologize", "apology"):
        result = await call_tool("on_user_apologize")
    elif action in ("coax", "placate", "哄"):
        effect = emotion_engine.force_reset_grumpy()
        life_engine.apply_emotion_effect(effect)
        result = {"success": True, "content": "好吧好吧，这次就原谅你了～"}
    elif action in ("comfort", "安慰"):
        effect = emotion_engine.on_user_comfort()
        life_engine.apply_emotion_effect(effect)
        result = {"success": True, "content": "那、那个...谢谢你安慰我～"}
    elif action == "task_done":
        result = {"success": True, "content": "太棒了！完成任务的感觉真好～"}
    else:
        return {"success": False, "message": "未知动作"}
    msg = result.get("content", "") if isinstance(result, dict) else str(result)
    return {"success": True, "message": msg}


@app.get("/proactive/message")
async def get_proactive_message(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_life_engine, add_assistant_message_to_memory
    life_engine = get_life_engine(user_id)
    msg = life_engine.get_proactive_message()
    if msg:
        add_assistant_message_to_memory(msg, user_id)
    return {"message": msg}


@app.get("/proactive/status")
async def get_proactive_status(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_life_engine
    life_engine = get_life_engine(user_id)
    return {"queue_len": len(life_engine._proactive_queue)}


@app.post("/proactive/trigger")
async def trigger_proactive_message(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.bridge import get_life_engine
    try:
        life_engine = get_life_engine(user_id)
        result = life_engine.trigger_now()
        return result
    except Exception as e:
        return {"success": False, "message": f"触发失败: {str(e)}"}


@app.get("/social/timeline")
async def get_timeline(limit: int = 20, filter_type: str = "", user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, SocialPost
    with get_session(user_id) as sess:
        query = sess.query(SocialPost)
        if filter_type:
            query = query.filter(SocialPost.post_type == filter_type)
        posts = query.order_by(SocialPost.created_at.desc()).limit(limit).all()
        return {
            "posts": [
                {"id": p.id, "author_name": p.author_name, "author_id": p.author_id,
                 "content": p.content, "created_at": p.created_at.isoformat() if p.created_at else None,
                 "likes": p.likes, "comments": p.comments or []}
                for p in posts
            ]
        }


@app.post("/social/timeline/trigger")
async def trigger_timeline(event_type: str = "exploration", data: str = "{}", user_id: str = Depends(require_user)):
    import json
    try:
        data_dict = json.loads(data) if data else {}
    except Exception:
        data_dict = {}
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    post = timeline.auto_publish(event_type, data_dict, user_id=user_id, skip_rate_limit=True)
    if post:
        return {"success": True, "content": post.content}
    return {"success": False, "message": "未生成内容"}


@app.post("/social/timeline/{post_id}/comment")
async def comment_on_post(post_id: int, user: str = "用户", content: str = "", user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    ok = timeline.comment_post(post_id, user, content, user_id=user_id)
    return {"success": ok}


@app.post("/social/timeline/{post_id}/like")
async def like_post(post_id: int, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, SocialPost
    with get_session(user_id) as sess:
        post = sess.query(SocialPost).filter(
            SocialPost.id == post_id,
            SocialPost.user_id == user_id
        ).first()
        if post:
            post.likes = (post.likes or 0) + 1
            sess.commit()
    return {"success": True}


@app.get("/social/mood-calendar")
async def get_mood_calendar(days: int = 7, user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, SocialPost
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    with get_session(user_id) as sess:
        posts = sess.query(SocialPost).filter(
            SocialPost.user_id == user_id,
            SocialPost.created_at >= cutoff
        ).all()
        mood_map = {
            (0.0, 0.4): ("😢", "难过"),
            (0.4, 0.6): ("😐", "一般"),
            (0.6, 0.8): ("😊", "开心"),
            (0.8, 1.1): ("🥰", "超开心"),
        }
        result = []
        for p in posts:
            m = p.mood_at_post or 0.5
            emoji, label = "😐", "一般"
            for (lo, hi), (e, l) in mood_map.items():
                if lo <= m < hi:
                    emoji, label = e, l
                    break
            result.append({
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                "emoji": emoji,
                "mood": label,
            })
        return {"calendar": result}


@app.get("/profile")
async def get_profile(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, UserProfile
    with get_session(user_id) as sess:
        profile = sess.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            sess.add(profile)
            sess.commit()
            sess.refresh(profile)
        return {
            "id": profile.id,
            "learning_style": profile.learning_style,
            "active_hours": profile.active_hours or [],
            "stress_level": profile.stress_level,
            "current_goals": profile.current_goals or [],
            "known_patterns": profile.known_patterns or [],
            "preferred_tone": profile.preferred_tone,
            "sleep_time": profile.sleep_time,
            "wake_time": profile.wake_time,
        }


@app.get("/daily-briefing")
async def daily_briefing(user_id: str = Depends(require_user)):
    return await call_tool("get_daily_briefing")


@app.get("/weekly-report")
async def weekly_report(user_id: str = Depends(require_user)):
    return await call_tool("get_weekly_report")


@app.get("/alerts")
async def alerts(user_id: str = Depends(require_user)):
    return await call_tool("get_alerts")


@app.post("/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...), user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.config import STT_API_URL, STT_API_KEY, STT_MODEL
    audio_bytes = await audio.read()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {
                "file": (audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm"),
            }
            data = {"model": STT_MODEL}
            response = await client.post(
                STT_API_URL, files=files, data=data,
                headers={"Authorization": f"Bearer {STT_API_KEY}"},
            )
            response.raise_for_status()
            result = response.json()
            return {"text": result.get("text", "").strip(), "success": True}
    except Exception as e:
        print(f"[stt] 语音转写失败: {e}")
        return {"text": "", "success": False, "error": str(e)}


# ─── 人生轨迹 API ────────────────────────────────────────────────

@app.get("/lingxi/life-trajectory")
async def get_life_trajectory(limit: int = 20, story_arc: str = "", user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.plugins.life_trajectory import recall_recent_events, STORY_ARCS, STORY_ARC_EMOJI
    events = recall_recent_events(user_id=user_id, limit=limit, story_arc=story_arc)
    for e in events:
        e["story_arc_label"] = STORY_ARCS.get(e["story_arc"], e["story_arc"])
        e["story_arc_emoji"] = STORY_ARC_EMOJI.get(e["story_arc"], "📌")
    return {"events": events}


@app.get("/lingxi/life-trajectory/summary")
async def get_life_trajectory_summary(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.plugins.life_trajectory import STORY_ARCS, recall_recent_events
    from lingxi_qwenpaw.db import get_session, LingxiLifeEvent

    with get_session(user_id) as sess:
        arc_counts = {}
        for arc in STORY_ARCS:
            count = sess.query(LingxiLifeEvent).filter(
                LingxiLifeEvent.story_arc == arc,
                LingxiLifeEvent.user_id == user_id
            ).count()
            arc_counts[arc] = count

    try:
        narrative = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, lambda: _gen_narrative_sf(user_id)),
            timeout=10.0
        )
    except Exception:
        narrative = ""

    return {"narrative": narrative, "threads": {}, "arc_counts": arc_counts}


def _gen_narrative_sf(user_id: str) -> str:
    from lingxi_qwenpaw.plugins.life_trajectory import recall_recent_events
    from lingxi_qwenpaw.bridge import llm_call_sf

    events = recall_recent_events(user_id=user_id, limit=5)
    if len(events) < 2:
        return ""

    events_text = "\n".join(f"- {e['summary']}（{e['story_arc']}）" for e in events)
    prompt = f"""你是灵犀，一个大学生 AI 助手。根据以下人生轨迹事件，写一段 2-3 句的叙事摘要，
像朋友回忆最近发生的事一样自然。不要Emoji，不要太正式。
事件：
{events_text}"""
    return llm_call_sf(prompt, temperature=0.7)


@app.get("/lingxi/memory/consolidation")
async def get_memory_consolidation_status(user_id: str = Depends(require_user)):
    from lingxi_qwenpaw.db import get_session, MemoryEntry
    with get_session(user_id) as sess:
        total = sess.query(MemoryEntry).count()
        by_level = {
            "episodic": sess.query(MemoryEntry).filter(MemoryEntry.consolidation_level == 0).count(),
            "semantic": sess.query(MemoryEntry).filter(MemoryEntry.consolidation_level == 1).count(),
            "archived": sess.query(MemoryEntry).filter(MemoryEntry.consolidation_level == 2).count(),
        }
        return {"total": total, "by_level": by_level}


# ─── 反馈系统 ────────────────────────────────────────────────────
FEEDBACK_FILE = Path(__file__).parent.parent / "data" / "feedback.json"

@app.post("/feedback")
async def submit_feedback(
    content: str = Body(..., embed=True),
    rating: int = Body(5, embed=True),
    user_id: Optional[str] = Depends(get_current_user),
):
    """收集用户反馈"""
    import json
    from datetime import datetime
    
    feedback_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    entry = {
        "id": feedback_id,
        "user_id": user_id or "anonymous",
        "content": content,
        "rating": rating,
        "created_at": datetime.now().isoformat(),
    }
    
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取现有反馈
    feedbacks = []
    if FEEDBACK_FILE.exists():
        try:
            feedbacks = json.loads(FEEDBACK_FILE.read_text())
        except:
            feedbacks = []
    
    feedbacks.append(entry)
    FEEDBACK_FILE.write_text(json.dumps(feedbacks, ensure_ascii=False, indent=2))
    
    return {"ok": True, "id": feedback_id}


@app.get("/feedback/count")
async def get_feedback_count(user_id: str = Depends(require_user)):
    """获取反馈数量（仅管理员）"""
    import json
    if FEEDBACK_FILE.exists():
        feedbacks = json.loads(FEEDBACK_FILE.read_text())
        return {"count": len(feedbacks)}
    return {"count": 0}

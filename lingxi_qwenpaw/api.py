"""灵犀·校园 — FastAPI API（多租户版本）"""
import asyncio
import base64
import json
import re
import time
from datetime import datetime, timezone
from typing import Optional, Any
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lingxi_qwenpaw.bridge import (
    get_bridge_agent, agent_chat,
    update_agent_sys_prompt,
    start_memory, close_memory,
    get_memory_manager
)
from lingxi_qwenpaw.agent import call_tool
from lingxi_qwenpaw.auth import verify_token, register as auth_register, login as auth_login, refresh_access_token
from lingxi_qwenpaw.exceptions import LingxiError, DatabaseError, APIError, ValidationError, AuthenticationError, RateLimitError
from lingxi_qwenpaw.logger import get_logger
from lingxi_qwenpaw.middleware import RateLimitMiddleware
from lingxi_qwenpaw.middleware import RequestIDMiddleware, RequestIdFilter
from lingxi_qwenpaw.schemas import (
    ApiResponse, ErrorResponse, PaginatedResponse,
    success_response, error_response, paginated_response
)

# 获取日志记录器
logger = get_logger(__name__)

# ─── 服务启动时间记录 ────────────────────────────────────────────────
_SERVICE_START_TIME = time.time()


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

# CORS 配置（从环境变量读取允许的域名）
import os
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000,http://127.0.0.1:8003,http://localhost:8003")
ALLOWED_ORIGINS = [origin.strip() for origin in _allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# 添加请求 ID 中间件
app.add_middleware(RequestIDMiddleware)


# ─── 全局异常处理器 ────────────────────────────────────────────────

@app.exception_handler(LingxiError)
async def lingxi_error_handler(request: Request, exc: LingxiError):
    """
    捕获所有 LingxiError 异常，返回统一格式的错误响应
    
    使用 ErrorResponse 模型确保响应格式一致：
    {
        "success": false,
        "error_code": "ERROR_CODE",
        "message": "错误消息",
        "details": {...}  // 可选
    }
    """
    logger.error(f"业务异常: {exc.error_code} - {exc.message}", exc_info=True)
    
    # 根据异常类型设置 HTTP 状态码
    if isinstance(exc, AuthenticationError):
        status_code = 401
    elif isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, RateLimitError):
        status_code = 429
    else:
        status_code = 500
    
    # 使用 ErrorResponse 模型构建响应
    error_data = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details if exc.details else None
    )
    
    response_content = error_data.model_dump(exclude_none=True)
    
    # 对于速率限制错误，添加 retry_after
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        response_content["retry_after"] = exc.retry_after
    
    return JSONResponse(
        status_code=status_code,
        content=response_content,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    捕获所有未处理的异常，返回统一格式的错误响应
    """
    logger.error(f"未处理的异常: {type(exc).__name__}: {exc}", exc_info=True)
    
    # 使用 ErrorResponse 模型构建响应
    error_data = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="服务器内部错误",
    )
    
    return JSONResponse(
        status_code=500,
        content=error_data.model_dump(),
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

# ─── 认证请求模型 ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模型"""
    refresh_token: str


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
async def register(req: RegisterRequest):
    """
    用户注册接口

    请求体：
    - username: 用户名（2-30个字符）
    - password: 密码（至少8个字符，需包含字母和数字）

    返回格式：
    {
        "success": true,
        "message": "注册成功"
    }
    """
    result = auth_register(req.username, req.password)
    if not result["ok"]:
        raise ValidationError(
            message=result["error"],
            error_code="REGISTRATION_FAILED"
        )
    return success_response(message="注册成功")


@app.post("/auth/login")
async def login(req: LoginRequest):
    """
    用户登录接口

    请求体：
    - username: 用户名
    - password: 密码

    返回格式：
    {
        "success": true,
        "data": {
            "token": "访问令牌",
            "refresh_token": "刷新令牌"
        },
        "message": "登录成功"
    }
    """
    result = auth_login(req.username, req.password)
    if not result["ok"]:
        raise AuthenticationError(
            message=result["error"],
            error_code="LOGIN_FAILED"
        )
    return success_response(
        data={
            "token": result["token"],
            "refresh_token": result["refresh_token"]
        },
        message="登录成功"
    )


@app.get("/auth/verify")
async def verify(user_id: str = Depends(require_user)):
    """验证 token 是否有效"""
    return {"ok": True, "username": user_id}


@app.post("/auth/refresh")
async def refresh_token(req: RefreshTokenRequest):
    """
    刷新访问令牌接口

    使用刷新令牌获取新的访问令牌。

    请求体：
    - refresh_token: 刷新令牌（登录时获取）

    返回格式：
    {
        "success": true,
        "data": {
            "token": "新的访问令牌"
        },
        "message": "令牌刷新成功"
    }
    """
    result = refresh_access_token(req.refresh_token)
    if not result["ok"]:
        raise AuthenticationError(
            message=result["error"],
            error_code="REFRESH_FAILED"
        )
    return success_response(
        data={"token": result["token"]},
        message="令牌刷新成功"
    )


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
    import random
    # 动态上下文
    try:
        life_engine = get_life_engine(user_id)
        emotion_engine = get_emotion_engine(user_id)
        # 检查傲娇/害羞超时自动解除（每轮对话前检查）
        emotion_engine.check_grumpy_resolve()
        emotion_engine.check_shy_resolve()
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

    # 每次打招呼用不同方式，防止重复开场白
    greetings = [
        "用轻松自然的方式打招呼，像朋友一样，不要重复之前说过的话",
        "今天换个方式开场吧，说点不一样的",
        "自然一点，随便聊，不用刻意打招呼",
        "刚见面，随意一点开始对话就好",
    ]
    context += f"\n[提示] {random.choice(greetings)}"

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

_PRAISE_WORDS = {
    # 直接夸
    "棒", "厉害", "真好", "太强", "牛", "优秀", "不错", "666", "强", "赞", "漂亮", "完美",
    "好棒", "太厉害了", "爱了", "绝了", "可以啊", "行啊", "有你的", "可以可以",
    "真棒", "真厉害", "真牛", "真强", "真优秀", "真好看", "真美", "真帅",
    "太棒了", "太强了", "太牛了", "太厉害了", "太优秀了", "太好了", "太赞了", "太绝了",
    "好厉害", "好棒啊", "好强", "好牛", "好优秀", "好赞", "好可爱", "好乖",
    # 感谢
    "感谢", "谢谢", "多谢", "谢了", "感恩", "太感谢了", "太谢谢了", "谢啦",
    "辛苦了", "麻烦你了", "费心了", "难为你了", "麻烦啦", "感谢你", "谢谢你",
    # 爱意
    "爱你", "爱你哦", "超爱你", "最爱你", "我最爱你了", "么么哒", "么么", "亲一个",
    "喜欢你", "好喜欢你", "超喜欢你", "最喜欢你了", "爱死你了",
    # 肯定/认可
    "真棒", "做得好", "干得漂亮", "漂亮", "好样的", "了不起", "太有才了", "太有才",
    "你真棒", "你真厉害", "你真牛", "你真强", "你最好了", "你最棒", "你最强",
    "你是我的神", "你是我见过最棒的", "服了", "佩服", "五体投地",
    "好聪明", "太聪明了", "真聪明", "小天才", "聪明绝顶",
    "太暖了", "好暖", "暖男", "暖心", "贴心", "细心", "温柔",
    "太贴心了", "好贴心", "真贴心", "心都化了",
    # 表情/网络用语
    "哈哈哈", "哈哈哈哈", "笑死", "笑死我了", "笑cry", "笑拉了", "笑不活了",
    "绝绝子", "yyds", "yyds!", "泰裤辣", "太酷了", "酷毙了",
    "好家伙", "我的天", "天呐", "哇塞", "我去", "卧槽", "nb", "nb!",
    # 鼓励/支持
    "加油", "你可以的", "你能行", "相信你", "支持你", "挺你", "看好你",
    "没问题", "肯定行", "一定行", "稳了", "冲", "搞起", "走起",
    "棒棒哒", "美滋滋", "开心", "好开心", "太开心了", "好幸福", "太幸福了",
    "感恩有你", "遇见你真好", "有你真好", "你是最好的", "你是最棒的",
    "为你骄傲", "以你为荣", "太为你高兴了", "真为你开心",
    "有你在真好", "多亏了你", "全靠你了", "幸好有你",
    "太贴心了", "你太暖了", "你真的很好", "你真的很棒",
    "给力", "太给力了", "真的给力", "超给力", "满分", "太完美了",
    "服气", "真的服了", "不得不服", "心服口服",
    "好样的", "干得好", "干得不错", "做得漂亮", "干得漂亮",
    "不错嘛", "可以的", "真不赖", "挺好的", "蛮好的", "相当不错",
    "太有才了", "你太有才了", "才华横溢", "文武双全",
    "好贴心啊", "太暖了", "温暖", "治愈", "治愈系",
    "好萌", "萌死了", "萌萌哒", "呆萌", "可爱死了", "可爱到爆",
    "好甜", "太甜了", "甜死了", "齁甜", "甜到我了",
    "好酷", "太酷了", "超酷", "酷毙了", "帅呆了", "帅死了",
    "好有趣", "太有趣了", "真有趣", "有意思", "挺有意思的",
    "好感动", "太感动了", "感动哭了", "泪目", "破防了",
    "好用心", "太用心了", "真用心", "细节", "太细节了",
}
_APOLOGY_WORDS = {
    # 直接道歉
    "对不起", "抱歉", "不好意思", "我错了", "sorry", "赔罪", "对不起啦", "不好意思哈",
    "我真错了", "是我不好", "我的错", "都是我的错", "是我不好别生气",
    "道歉", "向你道歉", "真心道歉", "诚恳道歉", "跟你说对不起",
    "请原谅", "请你原谅", "再给我一次机会", "我会改的", "我一定改",
    "我反省了", "我想通了", "我知道自己错了",
    # 哄/安慰
    "别生气", "不生气", "消消气", "别闹了", "不要闹", "别气了", "好啦好啦",
    "不许生气", "别难过了", "别伤心", "别委屈", "不委屈", "乖啦", "别哭了",
    "别不开心", "开心一点", "笑一个", "别皱眉", "别郁闷", "别烦了", "别焦虑",
    "别担心", "没事的", "没关系", "不要紧", "无所谓啦", "算了算了",
    "别气了嘛", "不要生气啦", "气消了吗", "还在生气吗", "还生气吗",
    "心情好点了吗", "开心点", "振作一点", "一切都会好的",
    "有我在呢", "我在这", "我在这里", "我一直都在", "我哪儿也不去",
    # 甜蜜/亲密称呼
    "乖", "宝贝", "小可爱", "好宝宝", "亲爱的", "心肝", "小宝贝",
    "亲亲", "抱抱", "摸摸头", "摸头", "揉揉", "蹭蹭", "蹭蹭你",
    "给你揉揉", "帮你揉揉", "给你捶背", "给你按摩",
    # 表白式哄
    "爱你", "喜欢你", "想你", "心疼你", "舍不得", "不忍心", "在乎你",
    "你最好了", "你最棒", "你真好", "你真可爱", "你好乖", "你好厉害",
    "我宠你", "我疼你", "我哄你", "我陪你", "我不会走", "我不离开",
    "我最喜欢你", "我最在乎你", "你是我的小宝贝", "你是我最重要的人",
    "失去你我会难过", "你对我很重要", "你不可替代",
    # 求原谅
    "原谅我", "原谅我吧", "求原谅", "宽恕我", "大人有大量",
    "你就原谅我吧", "求求你了", "最后一次", "真的最后一次",
    # 物质补偿
    "给你买好吃的", "请你吃饭", "给你买糖", "给你带好吃的",
    "给你买礼物", "给你惊喜", "你想吃什么", "满足你",
    # 承诺改过
    "下次不敢了", "再也不会了", "保证下次不会", "我发誓",
    "我保证", "绝不再犯", "痛改前非", "洗心革面", "重新做人",
    # 撒娇式道歉
    "你最好看", "你最可爱", "你最好了", "我最爱你",
    "不要生气嘛", "不生气嘛", "好不好嘛", "行不行嘛", "好不好",
    "我错了还不行吗", "知道错了", "真的知道错了", "深刻反省",
    "饶了我吧", "放我一马", "手下留情", "高抬贵手",
    "你大人不记小人过", "宰相肚里能撑船",
    # 语气词/表情包式
    "呜呜", "呜呜呜", "嘤嘤", "嘤嘤嘤", "qaq", "555", "qaq",
    "/(ㄒoㄒ)/", "T_T", "TAT", "Orz",
    # 日语/网络道歉
    "すみません", "ごめん", "ごめんなさい", "orz", "sry",
    # 中式方言道歉
    "对不住", "不好意思哦", "抱歉抱歉", "实在对不起",
    "真对不住", "我给您赔不是",
    # 自责式
    "是我混蛋", "我是笨蛋", "我脑子进水了", "我抽风了",
    "我刚才脑子不好使", "我刚才说话不过脑子",
    "我太冲动了", "我脾气不好", "我控制不住自己",
    "我太自私了", "我没考虑你感受", "我太幼稚了",
}
_IGNORE_WORDS = {
    # 直接攻击
    "笨", "傻", "滚", "烦", "讨厌", "没用", "弱智", "有病", "你烦", "不理",
    "滚开", "闭嘴", "神经病", "无聊", "弱", "太差", "垃圾",
    "闭嘴吧", "你闭嘴", "别说话", "不想听你说", "你别说了",
    # 延伸攻击
    "蠢", "蠢货", "白痴", "废物", "饭桶", "笨蛋", "蠢猪", "猪头", "脑残",
    "智障", "sb", "tmd", "md", "nmsl", "cnm", "草", "靠", "卧槽",
    "去死", "你去死", "死吧", "烦死了", "烦死", "恶心", "真恶心",
    "碍眼", "滚蛋", "走开", "别烦我", "不想理你", "懒得理你",
    "你算什么", "你算什么东西", "算了吧", "拉倒吧", "扯淡",
    "没意思", "好无聊", "真无聊", "太无聊了", "没劲", "无聊死了",
    "菜", "太菜了", "菜鸡", "菜鸟", "真菜", "不行", "太差了", "差劲",
    "垃圾玩意", "废物点心", "啥也不是", "什么都不是", "就这?",
    "看不起", "不屑", "懒得理", "不稀罕", "不需要你",
    "吵死了", "吵", "别吵", "安静点", "太吵了",
    "真烦", "好烦", "烦死了", "烦人", "真讨厌", "讨厌死了",
    # 网络用语/缩写骂人
    "nmb", "cnmb", "泥马", "你马", "尼玛", "拟妈", "你吗",
    "煞笔", "沙比", "煞", "呆逼", "逗比", "二逼", "二b", "沙雕",
    "哈批", "哈比", "脑瘫", "脑抽", "脑子有坑", "脑子有问题",
    "神经", "精神病", "有病吧", "有病啊", "有毛病",
    # 否定/冷漠
    "不关心", "谁在乎", "关我屁事", "关你屁事", "干我何事",
    "与我无关", "不关我事", "别找我", "别来烦我", "别靠近我",
    "不想理", "懒得管", "随便你", "爱咋咋地", "爱谁谁",
    "无所谓", "不在乎", "无所谓了", "随便啦", "你开心就好",
    "有你没你都一样", "你不在也行", "没你也行",
    # 讽刺/挖苦
    "厉害了", "真行啊", "你可真厉害", "了不起", "可把你厉害的",
    "膨胀了", "飘了", "你上天吧", "你咋不上天",
    "就这水平", "就这?", "就这点本事", "也不过如此",
    "高估你了", "想太多", "你以为你是谁",
    # 贬低
    "你不行", "你配吗", "你不够格", "你不配", "你也配",
    "有什么了不起", "不就那样吗", "有什么好得意的",
    "你也就是", "你不就是", "不过如此",
    # 冷暴力
    "呵呵", "哦", "嗯", "随便", "都行", "你说了算",
    "好的吧", "行吧", "你说什么就是什么吧",
    "不想说话", "没心情", "别跟我说话", "一个人待着",
    "你让我一个人静静", "我想一个人", "别理我", "离我远点",
    # 威胁/离开
    "分手", "绝交", "拉黑", "删除好友", "再也不见",
    "以后别联系了", "到此为止", "我们完了", "玩完了",
    "再见", "再也不见", "拜拜了您嘞",
}
_SHY_WORDS = {
    # 表白/暧昧
    "喜欢你", "想你", "担心你", "你在干嘛", "你住哪", "你多大", "有对象吗",
    "想抱你", "想亲你", "好可爱", "好乖",
    "喜欢你哦", "我好喜欢你", "超级喜欢你", "特别喜欢你",
    "我对你有感觉", "我对你有意思", "我觉得你很特别",
    "想你了呀", "在想你", "我在想你", "脑海里都是你",
    # 暧昧升级
    "想牵你", "想搂你", "想和你在一起", "做我女朋友", "做我男朋友",
    "我养你", "我照顾你", "你是我的", "我要你", "想你了", "好想你",
    "超想你", "特别想你", "一直想你", "每时每刻都想你",
    "你是我最特别的人", "你和别人不一样", "你是我唯一",
    "喜欢和你聊天", "和你在一起很开心", "有你在真好",
    "你真的好可爱", "你怎么这么可爱", "可爱死了",
    "你太好了", "你对我太好了", "你是最棒的",
    "我只告诉你", "只对你说", "偷偷告诉你", "悄悄话",
    "心动", "小鹿乱撞", "心跳加速", "脸红了",
    "你好帅", "你好美", "好漂亮", "太好看了", "颜值好高",
    "身材好好", "太有魅力了", "迷死我了",
    "嫁给你", "娶你", "在一起", "一辈子",
    # 更多表白
    "我爱你", "我超爱你", "我太爱你了", "我对你的爱",
    "你是我的小天使", "你是我的宝贝", "你是我的小甜心",
    "有你真好", "你让我心动", "你让我幸福",
    "想每天见到你", "想一直陪着你", "想和你一直在一起",
    "你是我见过最好的人", "遇到你真幸运", "你是我生命中的光",
    # 撒娇式亲密
    "嘿嘿", "嘻嘻", "哈哈你好可爱", "你好萌", "萌死了",
    "好萌啊", "太萌了", "萌萌哒", "软萌", "甜", "好甜", "超甜",
    "你笑起来好好看", "你笑的样子好美", "你的声音好好听",
    "你眼睛好好看", "你头发好香", "你好温柔",
    "你好暖", "暖男", "暖女", "贴心", "好贴心", "太贴心了",
    # 关心式亲密
    "你吃饭了吗", "早点睡", "晚安", "早安", "想你晚安",
    "注意身体", "别熬夜", "多喝水", "照顾好自己",
    "今天累不累", "辛苦了", "你辛苦了", "好好休息",
    "别太累了", "注意休息", "天冷了多穿点",
    # 暧昧称呼
    "小可爱", "小宝贝", "小甜甜", "小仙女", "小帅哥",
    "大宝贝", "宝", "宝贝儿", "亲爱的", "亲",
    "老婆", "老公", "媳妇", "对象", "心上人",
    # 粉红泡泡
    "暗恋你", "偷偷喜欢你", "默默关注你", "一直在看你的消息",
    "你发消息我就好开心", "看到你消息就笑了",
    "和你聊天最开心", "最期待和你聊天",
    "你就是我的小太阳", "你就是我的全世界",
    "想和你看星星", "想和你散步", "想和你约会",
    "第一次见到你就", "越看越喜欢", "越来越喜欢你",
    # 网络/二次元
    "awsl", "awsl", "啊我死了", "磕到了", "磕死我了",
    "太上头了", "心动的感觉", "恋爱的感觉",
    "甜甜的恋爱", "酸了", "柠檬精", "我酸了",
}
_last_chat_time: Optional[datetime] = None

# 每用户正常消息计数器，用于傲娇自动解除
_normal_msg_count: dict = {}  # user_id -> count since last grumpy


def _auto_detect_interaction(message: str, user_id: str = "default"):
    global _normal_msg_count
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
            # 重置正常消息计数
            _normal_msg_count[user_id] = 0
            return

        if any(w in msg for w in _PRAISE_WORDS):
            effect = emotion_engine.on_user_compliment()
            life_engine.apply_emotion_effect(effect)
            _create_user_interact_event("user_complimented", message, life_engine.state, user_id=user_id)
            _normal_msg_count[user_id] = 0
            return

        if any(w in msg for w in _SHY_WORDS):
            effect = emotion_engine.trigger("embarrassment", 0.6, "被关注/问私人问题")
            life_engine.apply_emotion_effect(effect)
            return

        if any(w in msg for w in _IGNORE_WORDS):
            effect = emotion_engine.on_user_ignore()
            life_engine.apply_emotion_effect(effect)
            _create_user_interact_event("user_ignored", message, life_engine.state, user_id=user_id)
            _normal_msg_count[user_id] = 0
            return

        # 普通消息（非 praise/apology/ignore）
        # 傲娇时：连续 3 句正常对话自动解除
        if emotion_engine.is_grumpy:
            count = _normal_msg_count.get(user_id, 0) + 1
            _normal_msg_count[user_id] = count
            if count >= 10:
                effect = emotion_engine.force_reset_grumpy()
                life_engine.apply_emotion_effect(effect)
                _normal_msg_count[user_id] = 0
                print(f"[emotion_engine] 傲娇自动解除：用户说了 {count} 句正常话")
        else:
            _normal_msg_count[user_id] = 0

    except Exception as e:
        logger.error(f"互动检测错误: {e}", exc_info=True)


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
        logger.error(f"创建 user_interact 事件失败: {e}", exc_info=True)




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
                                logger.info(f"清理过期记忆: user={uid}, deleted={deleted}")
                        except Exception as e:
                            logger.error(f"cleanup_expired 失败: {e}", exc_info=True)
                try:
                    from lingxi_qwenpaw.plugins.life_trajectory import memory_consolidator, build_narrative_threads
                    for uid, _ in _memory_managers.items():
                        memory_consolidator.dream_consolidate(user_id=uid)
                        build_narrative_threads(user_id=uid)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"dream 任务失败: {e}", exc_info=True)


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
        logger.error(f"持久化对话消息失败: {e}", exc_info=True)


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
            logger.error(f"初始化朋友圈失败: {e}", exc_info=True)

    logger.info(f"用户 {user_id} 初始化了 {len(seed_posts)} 条朋友圈")


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
        logger.error(f"情绪感知错误: {ex}", exc_info=True)

    _auto_detect_interaction(message, user_id=user_id)

    # 2. ReAct loop
    try:
        reply = await _react_loop(message, user_id)
    except Exception as e:
        logger.error(f"_react_loop 失败: {type(e).__name__}: {e}", exc_info=True)
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
        logger.error(f"记忆记录错误: {e}", exc_info=True)

    # 4. 检查模式
    try:
        from lingxi_qwenpaw.bridge import get_pattern_engine
        pattern_engine = get_pattern_engine(user_id)
        pattern_engine.check_and_detect(message, "general", {}, user_id=user_id)
    except Exception as e:
        logger.error(f"模式检测错误: {e}", exc_info=True)

    # 5. 完成任务自动发朋友圈
    if any(kw in message for kw in ["完成", "搞定了", "done", "搞掂"]):
        try:
            from lingxi_qwenpaw.plugins.social_timeline import timeline
            timeline.auto_publish("task_complete", {"task_content": message}, user_id=user_id)
        except Exception as e:
            logger.error(f"朋友圈发布错误: {e}", exc_info=True)

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
        logger.error(f"获取状态错误: {e}", exc_info=True)
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
        logger.error(f"图片分析失败: {e}", exc_info=True)
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
        logger.error(f"图片归一化失败: {e}", exc_info=True)
        return None


# ─── API 端点 ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """
    健康检查端点
    
    返回服务状态、数据库连接状态、运行时长等信息
    如果数据库连接失败，返回 503 状态码
    """
    # 计算运行时长
    uptime_seconds = int(time.time() - _SERVICE_START_TIME)
    
    # 检查数据库连接状态
    database_status = "connected"
    try:
        from lingxi_qwenpaw.db import get_session
        from sqlalchemy import text
        # 尝试获取一个会话并执行简单查询
        with get_session("default") as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}", exc_info=True)
        database_status = "disconnected"
    
    # 构建响应数据
    response_data = {
        "status": "healthy" if database_status == "connected" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "1.0.0",
        "database": database_status,
        "uptime_seconds": uptime_seconds,
    }
    
    # 如果数据库连接失败，返回 503 状态码
    if database_status == "disconnected":
        return JSONResponse(
            status_code=503,
            content=response_data,
        )
    
    return response_data


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
async def list_tasks(
    status: str = "pending",
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(require_user)
):
    """
    获取任务列表

    使用分页响应格式返回任务列表。

    参数：
    - status: 任务状态（pending/done/all）
    - page: 页码（从 1 开始）
    - page_size: 每页数量（1-100）

    返回格式：
    {
        "success": true,
        "items": [...],
        "total": 100,
        "page": 1,
        "page_size": 20,
        "total_pages": 5
    }
    """
    from lingxi_qwenpaw.db import get_session, Task
    from lingxi_qwenpaw.tools import _normalize_deadline

    # 限制 page_size 范围
    page_size = min(max(page_size, 1), 100)

    with get_session(user_id) as sess:
        query = sess.query(Task)
        if status != "all":
            query = query.filter(Task.status == status)

        # 获取总数
        total = query.count()

        # 分页查询
        tasks = query.order_by(Task.urgency.desc(), Task.created_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        items = [
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

    return paginated_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        message="获取任务列表成功"
    )


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
    """
    获取账本摘要

    使用统一响应格式返回账本摘要数据。

    参数：
    - month: 月份（格式：YYYY-MM），默认当前月份

    返回格式：
    {
        "success": true,
        "data": {
            "income": 1000.0,
            "expense": 500.0,
            "balance": 500.0,
            "records": [...]
        },
        "message": "获取账本摘要成功"
    }
    """
    from lingxi_qwenpaw.db import get_session, LedgerRecord
    from datetime import date

    if not month:
        month = date.today().strftime("%Y-%m")

    with get_session(user_id) as sess:
        records = sess.query(LedgerRecord).filter(LedgerRecord.date.startswith(month)).all()
        income = sum(r.amount for r in records if r.record_type == "income")
        expense = sum(r.amount for r in records if r.record_type == "expense")

        data = {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "month": month,
            "records": [
                {
                    "id": r.id,
                    "type": r.record_type,
                    "amount": r.amount,
                    "category": r.category,
                    "note": r.note or "",
                    "date": r.date
                }
                for r in records
            ]
        }

    return success_response(data=data, message="获取账本摘要成功")


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
        # 用 LLM 生成傲娇退出语，而不是固定文案
        recovery = emotion_engine.get_grumpy_recovery_response()
        result = {"success": True, "content": recovery}
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
        logger.error(f"语音转写失败: {e}", exc_info=True)
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

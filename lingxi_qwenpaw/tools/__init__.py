"""灵犀·校园 — Tools 注册（暴露灵魂引擎给 agent）"""
from datetime import datetime, date, timedelta
from typing import Any
import json
import re


def _success(content: str) -> dict:
    return {"success": True, "content": content}


# ─── 日期归一化 ────────────────────────────────────────────────────

_WEEKDAY_MAP = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

def _normalize_deadline(raw: str) -> str:
    """将中文相对日期转为 ISO 格式 (YYYY-MM-DD)。
    如果已经是 ISO 格式或无法解析，原样返回。"""
    if not raw or not raw.strip():
        return ""
    s = raw.strip()
    # 已经是 ISO 格式
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    today = date.today()
    # 去掉时间部分（下午3点、晚上、上午 等）— 只匹配完整时间词
    s_date = re.sub(r"(?:上午|下午|晚上|早上|中午)\s*\d*[点时:]?\d*[分]?", "", s).strip()
    if "今天" in s_date or "今晚" in s:
        return today.isoformat()
    if "明天" in s_date:
        return (today + timedelta(days=1)).isoformat()
    if "大后天" in s_date:
        return (today + timedelta(days=3)).isoformat()
    if "后天" in s_date:
        return (today + timedelta(days=2)).isoformat()
    # 下周X
    m = re.search(r"下周([一二三四五六日天])", s_date)
    if m:
        target = _WEEKDAY_MAP[m.group(1)]
        days_ahead = (target - today.weekday()) % 7 + 7
        return (today + timedelta(days=days_ahead)).isoformat()
    # 本周X / 周X（取最近的未来日期）
    m = re.search(r"(?:本)?周([一二三四五六日天])", s_date)
    if m:
        target = _WEEKDAY_MAP[m.group(1)]
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # 如果就是今天，取下周
        return (today + timedelta(days=days_ahead)).isoformat()
    # X月Y日 / X月Y号
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", s_date)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year
        try:
            d = date(year, month, day)
            if d < today:
                d = date(year + 1, month, day)
            return d.isoformat()
        except ValueError:
            pass
    # N天后
    m = re.search(r"(\d+)\s*天后", s_date)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    return s  # 无法解析，原样返回


def _error(content: str) -> dict:
    return {"success": False, "content": content}


# ─── 情绪相关 Tools ───────────────────────────────────────────────

async def get_emotion_status(user_id: str = "default") -> dict:
    """获取当前情绪状态"""
    from lingxi_qwenpaw.bridge import get_emotion_engine
    emotion_engine = get_emotion_engine(user_id)
    return _success(json.dumps(emotion_engine.get_state(), ensure_ascii=False, indent=2))


async def perceive_user_emotion(message: str, user_id: str = "default") -> dict:
    """分析用户消息的情绪"""
    from lingxi_qwenpaw.bridge import get_emotion_engine
    emotion_engine = get_emotion_engine(user_id)
    emotion = emotion_engine.perceive_user_emotion(message)
    if emotion:
        return _success(f"用户情绪：{emotion}")
    return _success("未检测到明确情绪")


async def on_user_apologize(user_id: str = "default") -> dict:
    """用户道歉"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    effect = emotion_engine.on_user_apologize()
    life_engine.apply_emotion_effect(effect)
    return _success("傲娇已解除，灵犀感到被原谅 🙏")


async def on_user_compliment(user_id: str = "default") -> dict:
    """用户夸奖"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    effect = emotion_engine.on_user_compliment()
    life_engine.apply_emotion_effect(effect)
    return _success("灵犀感到很开心，有点害羞 😊")


async def on_user_ignore(user_id: str = "default") -> dict:
    """用户忽略灵犀"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    effect = emotion_engine.on_user_ignore()
    life_engine.on_user_ignore()
    life_engine.apply_emotion_effect(effect)
    state = emotion_engine.get_state()
    if state["is_grumpy"]:
        return _success(f"灵犀不高兴了：{state['grumpy_reason']}")
    return _success("灵犀有点难过...")


async def coax_lingxi(user_id: str = "default") -> dict:
    """哄灵犀（强制清除傲娇状态）"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    if not emotion_engine.is_grumpy:
        return _success("灵犀现在没有闹脾气哦～")
    effect = emotion_engine.force_reset_grumpy()
    life_engine.apply_emotion_effect(effect)
    return _success("好吧好吧，这次就原谅你了～ 😊")


async def comfort_lingxi(user_id: str = "default") -> dict:
    """安慰灵犀（清除害羞状态）"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    if not emotion_engine.is_shy:
        return _success("灵犀现在没有害羞哦～")
    effect = emotion_engine.on_user_comfort()
    life_engine.apply_emotion_effect(effect)
    return _success("那、那个...谢谢你安慰我 😊")


# ─── 生命引擎相关 Tools ───────────────────────────────────────────

async def get_life_status(user_id: str = "default") -> dict:
    """获取灵犀生命状态"""
    from lingxi_qwenpaw.bridge import get_life_engine
    life_engine = get_life_engine(user_id)
    return _success(json.dumps(life_engine.get_state(), ensure_ascii=False, indent=2))


async def get_behavior_context(user_id: str = "default") -> dict:
    """获取行为提示（注入 agent prompt）"""
    from lingxi_qwenpaw.bridge import get_life_engine, get_emotion_engine
    life_engine = get_life_engine(user_id)
    emotion_engine = get_emotion_engine(user_id)
    life_prompt = life_engine.get_behavior_prompt()
    emotion_prompt = emotion_engine.get_behavior_prompt()
    combined = f"{life_prompt}；{emotion_prompt}"
    return _success(combined)


async def get_proactive_message(user_id: str = "default") -> dict:
    """取出主动消息队列（用于推送）"""
    from lingxi_qwenpaw.bridge import get_life_engine
    life_engine = get_life_engine(user_id)
    msg = life_engine.get_proactive_message()
    if msg:
        return _success(msg)
    return _success("")


async def on_user_message(message: str, user_id: str = "default") -> dict:
    """用户发消息 → 更新生命状态"""
    from lingxi_qwenpaw.bridge import get_life_engine
    life_engine = get_life_engine(user_id)
    life_engine.on_user_message(message)
    return _success("状态已更新")


# ─── 记忆相关 Tools ────────────────────────────────────────────────

async def recall_memories(query: str, layers: str = "", limit: int = 8, user_id: str = "default") -> dict:
    """召回相关记忆"""
    from lingxi_qwenpaw.bridge import get_memory_layer
    memory_layer = get_memory_layer(user_id)
    layer_list = layers.split(",") if layers else None
    results = memory_layer.recall(query, layer_list, limit, user_id=user_id)
    if not results:
        return _success("暂无相关记忆")
    preview = "\n".join(f"• {r['content'][:50]}" for r in results[:5])
    return _success(f"相关记忆：\n{preview}")


async def record_interaction(user_message: str, intent: str, entities_json: str = "{}", response: str = "", user_id: str = "default") -> dict:
    """记录本次交互到记忆"""
    from lingxi_qwenpaw.bridge import get_memory_layer
    memory_layer = get_memory_layer(user_id)
    try:
        entities = json.loads(entities_json)
    except Exception:
        entities = {}
    memory_layer.record_interaction(user_message, intent, entities, response, user_id=user_id)
    return _success("已记录到记忆")


async def get_memory_context(query: str = "", intent: str = "", user_id: str = "default") -> dict:
    """获取注入 LLM 的记忆上下文"""
    from lingxi_qwenpaw.bridge import get_memory_layer
    memory_layer = get_memory_layer(user_id)
    context = memory_layer.get_context_for_llm(query, intent, user_id=user_id)
    return _success(context or "暂无相关记忆")


# ─── 朋友圈相关 Tools ──────────────────────────────────────────────

async def publish_timeline_post(content: str, post_type: str = "daily_life", mood: float = 2.0, energy: float = 85.0, user_id: str = "default") -> dict:
    """发布朋友圈"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    post = timeline.publish(content, post_type, user_id=user_id, mood=mood, energy=energy)
    return _success(f"已发布朋友圈（{post.post_type}）：{post.content[:30]}...")


async def auto_publish(event_type: str, data_json: str = "{}", user_id: str = "default") -> dict:
    """根据事件类型自动发布朋友圈"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    try:
        data = json.loads(data_json)
    except Exception:
        data = {}
    post = timeline.auto_publish(event_type, data, user_id=user_id)
    if post:
        return _success(f"已自动发布朋友圈：{post.content[:30]}...")
    return _success("未触发自动发布")


async def get_timeline(limit: int = 20, filter_type: str = "", user_id: str = "default") -> dict:
    """获取朋友圈列表"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    posts = timeline.get_timeline(limit, filter_type or None, user_id=user_id)
    if not posts:
        return _success("朋友圈空空如也～")
    lines = []
    for p in posts:
        time_str = p.created_at.strftime("%m-%d %H:%M") if hasattr(p.created_at, 'strftime') else str(p.created_at)
        lines.append(f"[{time_str}] {p.author_name}：{p.content[:40]}...")
    return _success("\n".join(lines))


async def like_timeline_post(post_id: int, user_id: str = "default") -> dict:
    """点赞朋友圈"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    ok = timeline.like_post(post_id, user_id=user_id)
    return _success("已点赞" if ok else "点赞失败")


async def comment_timeline_post(post_id: int, user: str, content: str, user_id: str = "default") -> dict:
    """评论朋友圈"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    ok = timeline.comment_post(post_id, user, content, user_id=user_id)
    return _success("已评论" if ok else "评论失败")


async def get_mood_calendar(days: int = 7, user_id: str = "default") -> dict:
    """获取情绪日历"""
    from lingxi_qwenpaw.plugins.social_timeline import timeline
    data = timeline.get_mood_calendar(days, user_id=user_id)
    if not data:
        return _success("暂无情绪数据")
    lines = [f"{d['date']}: {d.get('mood', '?')}" for d in data]
    return _success("\n".join(lines))


# ─── 模式检测相关 Tools ────────────────────────────────────────────

async def get_patterns(user_id: str = "default") -> dict:
    """获取活跃行为模式"""
    from lingxi_qwenpaw.bridge import get_pattern_engine
    pattern_engine = get_pattern_engine(user_id)
    patterns = pattern_engine.get_active_patterns(user_id=user_id)
    if not patterns:
        return _success("未检测到行为模式")
    lines = [f"• {p['description']}（{p['lifecycle_stage']}）" for p in patterns]
    return _success("\n".join(lines))


async def check_patterns(user_message: str, intent: str, entities_json: str = "{}", user_id: str = "default") -> dict:
    """检测行为模式"""
    from lingxi_qwenpaw.bridge import get_pattern_engine
    pattern_engine = get_pattern_engine(user_id)
    try:
        entities = json.loads(entities_json)
    except Exception:
        entities = {}
    detected = pattern_engine.check_and_detect(user_message, intent, entities, user_id=user_id)
    if detected:
        return _success(f"检测到模式：{detected[0]['description']}")
    return _success("未检测到新模式")


async def get_insights(unread_only: bool = False, user_id: str = "default") -> dict:
    """获取洞察"""
    from lingxi_qwenpaw.bridge import get_pattern_engine
    pattern_engine = get_pattern_engine(user_id)
    insights = pattern_engine.get_insights(unread_only, user_id=user_id)
    if not insights:
        return _success("暂无洞察")
    lines = [f"[{i['type']}] {i['content']}" for i in insights[:5]]
    return _success("\n".join(lines))


# ─── 任务相关 Tools ────────────────────────────────────────────────

async def create_task(content: str, urgency: int = 3, deadline: str = "", effort: str = "medium", tags_json: str = "[]", user_id: str = "default") -> dict:
    """创建任务。deadline 必须是 YYYY-MM-DD 格式，支持中文相对日期（明天、下周三、5月10日 等）"""
    from lingxi_qwenpaw.db import get_session, Task
    try:
        tags = json.loads(tags_json)
    except Exception:
        tags = []
    deadline = _normalize_deadline(deadline)
    with get_session(user_id) as sess:
        task = Task(user_id=user_id, content=content, urgency=urgency, deadline=deadline, effort=effort, tags=tags)
        sess.add(task)
        sess.commit()
        return _success(f"已创建任务：{content}（截止：{deadline or '无'}）")


async def list_tasks(status: str = "pending", limit: int = 20, user_id: str = "default") -> dict:
    """列出任务"""
    from lingxi_qwenpaw.db import get_session, Task
    with get_session(user_id) as sess:
        q = sess.query(Task).filter(Task.user_id == user_id)
        if status != "all":
            q = q.filter(Task.status == status)
        tasks = q.order_by(Task.urgency.desc(), Task.created_at.desc()).limit(limit).all()
        if not tasks:
            return _success("没有任务")
        lines = [f"{t.id}. [{t.status}] {t.content}" + (f" (截止:{t.deadline})" if t.deadline else "") for t in tasks]
        return _success("\n".join(lines))


async def complete_task(task_id: int, user_id: str = "default") -> dict:
    """完成任务"""
    from lingxi_qwenpaw.db import get_session, Task
    with get_session(user_id) as sess:
        task = sess.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            return _error(f"任务 {task_id} 不存在")
        task.status = "done"
        task.done_at = datetime.utcnow()
        sess.commit()
        return _success(f"已完成：{task.content}")


async def defer_task(task_id: int, days: int = 1, user_id: str = "default") -> dict:
    """推迟任务"""
    from lingxi_qwenpaw.db import get_session, Task
    from datetime import date, timedelta
    with get_session(user_id) as sess:
        task = sess.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            return _error(f"任务 {task_id} 不存在")
        if task.deadline:
            old = date.fromisoformat(task.deadline)
            task.deadline = (old + timedelta(days=days)).isoformat()
        else:
            task.deadline = (date.today() + timedelta(days=days)).isoformat()
        task.deferred_to = (date.today() + timedelta(days=days)).isoformat()
        task.status = "deferred"
        sess.commit()
        return _success(f"已推迟 {days} 天：{task.content}")


# ─── 时间记录 Tools ────────────────────────────────────────────────

async def log_time(category: str, minutes: int, note: str = "", user_id: str = "default") -> dict:
    """记录时间"""
    from lingxi_qwenpaw.db import get_session, TimeLog
    from datetime import date
    with get_session(user_id) as sess:
        log = TimeLog(user_id=user_id, category=category, minutes=minutes, note=note, date=date.today().isoformat())
        sess.add(log)
        sess.commit()
        return _success(f"已记录：{category} {minutes}分钟")


async def get_time_summary(days: int = 7, user_id: str = "default") -> dict:
    """获取时间汇总"""
    from lingxi_qwenpaw.db import get_session, TimeLog
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    with get_session(user_id) as sess:
        logs = sess.query(TimeLog).filter(
            TimeLog.user_id == user_id,
            TimeLog.date >= cutoff.isoformat()
        ).all()
        if not logs:
            return _success("暂无时间记录")
        summary: dict = {}
        for log in logs:
            summary[log.category] = summary.get(log.category, 0) + log.minutes
        lines = [f"• {cat}: {mins}分钟" for cat, mins in sorted(summary.items(), key=lambda x: -x[1])]
        total = sum(summary.values())
        lines.append(f"合计: {total}分钟")
        return _success("\n".join(lines))


# ─── 日记 Tools ────────────────────────────────────────────────────

async def add_journal(text: str, user_id: str = "default") -> dict:
    """写日记"""
    from lingxi_qwenpaw.db import get_session, JournalEntry
    from datetime import date
    with get_session(user_id) as sess:
        entry = JournalEntry(user_id=user_id, date=date.today().isoformat(), text=text)
        sess.add(entry)
        sess.commit()
        return _success(f"日记已保存：{text[:30]}...")


async def get_journals(limit: int = 7, user_id: str = "default") -> dict:
    """获取日记"""
    from lingxi_qwenpaw.db import get_session, JournalEntry
    with get_session(user_id) as sess:
        entries = sess.query(JournalEntry).filter(
            JournalEntry.user_id == user_id
        ).order_by(JournalEntry.created_at.desc()).limit(limit).all()
        if not entries:
            return _success("暂无日记")
        lines = [f"[{e.date}] {e.text[:50]}" for e in entries]
        return _success("\n".join(lines))


# ─── 记账 Tools ────────────────────────────────────────────────────

async def add_ledger(record_type: str, amount: float, category: str, note: str = "", user_id: str = "default") -> dict:
    """记账"""
    from lingxi_qwenpaw.db import get_session, LedgerRecord
    from datetime import date
    with get_session(user_id) as sess:
        record = LedgerRecord(
            user_id=user_id, record_type=record_type, amount=amount, category=category,
            note=note, date=date.today().isoformat()
        )
        sess.add(record)
        sess.commit()
        return _success(f"已记账：{record_type} {amount}元（{category}）")


async def get_ledger_summary(month: str = "", user_id: str = "default") -> dict:
    """获取月度财务汇总"""
    from lingxi_qwenpaw.db import get_session, LedgerRecord
    if not month:
        from datetime import date
        month = date.today().strftime("%Y-%m")
    with get_session(user_id) as sess:
        records = sess.query(LedgerRecord).filter(
            LedgerRecord.user_id == user_id,
            LedgerRecord.date.startswith(month)
        ).all()
        if not records:
            return _success(f"{month} 暂无记账记录")
        income = sum(r.amount for r in records if r.record_type == "income")
        expense = sum(r.amount for r in records if r.record_type == "expense")
        lines = [f"收入: {income}元", f"支出: {expense}元", f"结余: {income - expense}元"]
        return _success("\n".join(lines))


# ─── 报告 Tools ────────────────────────────────────────────────────

async def get_daily_briefing(user_id: str = "default") -> dict:
    """获取今日简报"""
    from lingxi_qwenpaw.db import get_session, Task, TimeLog, JournalEntry
    from datetime import date, timedelta
    from lingxi_qwenpaw.config import TIME_CATEGORIES

    today = date.today()

    # 今日任务
    with get_session(user_id) as sess:
        tasks = sess.query(Task).filter(
            Task.user_id == user_id,
            Task.status.in_(["pending", "deferred"]),
            (Task.deadline == today.isoformat()) | (Task.deadline < today.isoformat())
        ).order_by(Task.urgency.desc()).limit(10).all()
        task_lines = [t.content for t in tasks] or ["今日无截止任务"]

        # 今日时间
        logs = sess.query(TimeLog).filter(
            TimeLog.user_id == user_id,
            TimeLog.date == today.isoformat()
        ).all()
        time_by_cat = {}
        for log in logs:
            time_by_cat[log.category] = time_by_cat.get(log.category, 0) + log.minutes
        time_lines = []
        for cat, mins in sorted(time_by_cat.items(), key=lambda x: -x[1]):
            h, m = mins // 60, mins % 60
            time_lines.append(f"  • {TIME_CATEGORIES.get(cat, cat)}: {h}h{m:02d}m")
        time_str = "\n".join(time_lines) or "  暂无记录"

        # 停滞检测
        alerts = []
        for cat_key in ["thesis", "homework"]:
            cutoff = (today - timedelta(days=3)).isoformat()
            exists = sess.query(TimeLog).filter(
                TimeLog.user_id == user_id,
                TimeLog.category == cat_key, TimeLog.date >= cutoff
            ).count() > 0
            if not exists:
                alerts.append(f"{TIME_CATEGORIES.get(cat_key, cat_key)}已停滞3天")

    briefing = f"""☀️ 今日简报 {today.strftime('%m月%d日')}
📋 待办任务：
  {"  ".join(task_lines)}
⏱️ 今日时间：
{time_str}"""
    if alerts:
        briefing += "\n⚠️ " + "\n⚠️ ".join(alerts)
    return _success(briefing)


async def get_weekly_report(user_id: str = "default") -> dict:
    """获取本周报告"""
    from lingxi_qwenpaw.db import get_session, TimeLog, JournalEntry, Task
    from datetime import date, timedelta
    from lingxi_qwenpaw.config import TIME_CATEGORIES

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_str = start_of_week.strftime("%m月%d日") + "-" + today.strftime("%m月%d日")

    with get_session(user_id) as sess:
        logs = sess.query(TimeLog).filter(
            TimeLog.user_id == user_id,
            TimeLog.date >= start_of_week.isoformat(),
            TimeLog.date <= today.isoformat()
        ).all()
        time_by_cat = {}
        for log in logs:
            time_by_cat[log.category] = time_by_cat.get(log.category, 0) + log.minutes
        total_mins = sum(time_by_cat.values())
        time_lines = []
        for cat, mins in sorted(time_by_cat.items(), key=lambda x: -x[1]):
            h, m = mins // 60, mins % 60
            pct = mins / max(total_mins, 1) * 100
            bar = "█" * int(pct // 10)
            time_lines.append(f"  {TIME_CATEGORIES.get(cat, cat):6s} {bar:10s} {h}h{m:02d}m ({pct:.0f}%)")

        done_count = sess.query(Task).filter(Task.user_id == user_id, Task.status == "done").count()
        pending_count = sess.query(Task).filter(Task.user_id == user_id, Task.status == "pending").count()

    report = f"""📅 本周 {week_str}
⏱️ 时间分布：
{chr(10).join(time_lines) or '  暂无记录'}
📊 任务完成：{done_count}个 | 待办：{pending_count}个"""
    return _success(report)


async def get_alerts(user_id: str = "default") -> dict:
    """获取当前活跃告警"""
    from lingxi_qwenpaw.db import get_session, TimeLog, Task
    from datetime import date, timedelta
    from lingxi_qwenpaw.config import TIME_CATEGORIES

    alerts = []
    today = date.today()

    with get_session(user_id) as sess:
        # 停滞告警
        for cat_key in ["thesis", "homework", "prep"]:
            cutoff = (today - timedelta(days=3)).isoformat()
            exists = sess.query(TimeLog).filter(
                TimeLog.user_id == user_id,
                TimeLog.category == cat_key, TimeLog.date >= cutoff
            ).count() > 0
            if not exists:
                alerts.append({
                    "type": "stagnation",
                    "message": f"{TIME_CATEGORIES.get(cat_key, cat_key)}已停滞3天",
                })

        # 欲望冷静期
        wants = sess.query(Task).filter(
            Task.user_id == user_id, Task.item_type == "want", Task.status == "pending"
        ).all()
        for w in wants:
            if w.created_at:
                days_since = (today - w.created_at.date()).days
                cool_off = 7 - days_since
                if 0 < cool_off <= 2:
                    alerts.append({
                        "type": "want_cooling",
                        "message": f"「{w.content}」冷静期还剩{cool_off}天",
                        "task_id": w.id,
                    })

    return _success("\n".join([a["message"] for a in alerts]) if alerts else "暂无告警")


# ─── 获取灵犀状态总览 ─────────────────────────────────────────────

async def get_lingxi_status(user_id: str = "default") -> dict:
    """获取灵犀完整状态（情绪+生命）"""
    from lingxi_qwenpaw.bridge import get_emotion_engine, get_life_engine
    emotion_engine = get_emotion_engine(user_id)
    life_engine = get_life_engine(user_id)
    emotion_state = emotion_engine.get_state()
    life_state = life_engine.get_state()
    combined = {
        "emotion": emotion_state,
        "life": life_state,
    }
    return _success(json.dumps(combined, ensure_ascii=False, indent=2))


# ─── 注册所有 Tools ────────────────────────────────────────────────

async def vision_analyze(image_base64: str, question: str = "请详细描述这张图片的内容") -> dict:
    """分析图片内容（调用 Qwen3-VL 视觉模型）"""
    import httpx
    from lingxi_qwenpaw.api import _normalize_image
    from lingxi_qwenpaw.config import VISION_API_URL, VISION_API_KEY, VISION_MODEL

    try:
        normalized = _normalize_image(image_base64)
        if not normalized:
            return {"success": False, "content": "[图片解码失败，无法分析]"}

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
                                {"type": "text", "text": question},
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
            return _success(data["choices"][0]["message"]["content"])
    except Exception as e:
        return {"success": False, "content": f"[图片分析失败：{str(e)}]"}


TOOL_FUNCTIONS = {
    # 情绪
    "get_emotion_status": get_emotion_status,
    "perceive_user_emotion": perceive_user_emotion,
    "on_user_apologize": on_user_apologize,
    "on_user_compliment": on_user_compliment,
    "on_user_ignore": on_user_ignore,
    "coax_lingxi": coax_lingxi,
    "comfort_lingxi": comfort_lingxi,
    # 生命
    "get_life_status": get_life_status,
    "get_behavior_context": get_behavior_context,
    "get_proactive_message": get_proactive_message,
    "on_user_message": on_user_message,
    # 记忆
    "recall_memories": recall_memories,
    "record_interaction": record_interaction,
    "get_memory_context": get_memory_context,
    # 朋友圈
    "publish_timeline_post": publish_timeline_post,
    "auto_publish": auto_publish,
    "get_timeline": get_timeline,
    "like_timeline_post": like_timeline_post,
    "comment_timeline_post": comment_timeline_post,
    "get_mood_calendar": get_mood_calendar,
    # 模式
    "get_patterns": get_patterns,
    "check_patterns": check_patterns,
    "get_insights": get_insights,
    # 任务
    "create_task": create_task,
    "list_tasks": list_tasks,
    "complete_task": complete_task,
    "defer_task": defer_task,
    # 时间
    "log_time": log_time,
    "get_time_summary": get_time_summary,
    # 日记
    "add_journal": add_journal,
    "get_journals": get_journals,
    # 记账
    "add_ledger": add_ledger,
    "get_ledger_summary": get_ledger_summary,
    # 报告
    "get_daily_briefing": get_daily_briefing,
    "get_weekly_report": get_weekly_report,
    "get_alerts": get_alerts,
    # 总览
    "get_lingxi_status": get_lingxi_status,
    # 视觉
    "vision_analyze": vision_analyze,
}

#!/usr/bin/env python3
"""
时间黑洞追踪器 - CLI 工具
追踪时间花销，定位时间黑洞
"""

import json
import sys
import os
import argparse
from datetime import datetime, date, timedelta
from collections import defaultdict

DATA_FILE = os.path.join(os.path.dirname(__file__), "time_data.json")

# 类别定义：(emoji, 中文名, 简写)
CATEGORIES = {
    "tutoring": ("🔴", "上课", "课"),
    "commute": ("🟠", "通勤", "车"),
    "prep": ("🟡", "备课", "备"),
    "homework": ("🔵", "作业", "业"),
    "thesis": ("🟣", "毕设", "毕"),
    "content": ("🟢", "内容", "内"),
    "chore": ("⚪", "家务", "家"),
    "hygiene": ("⚪", "洗漱", "洗"),
    "meal": ("⚪", "吃饭", "饭"),
    "rest": ("⚪", "休息", "休"),
    "waste": ("⚫", "摸鱼", "摸"),
    "other": ("⚪", "其他", "—"),
}

# 杂项合并的类别
MISC_CATS = {"hygiene", "meal", "chore", "rest", "waste"}


def load_data():
    """加载数据文件，不存在则返回空结构"""
    if not os.path.exists(DATA_FILE):
        return {"logs": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("✗ 数据文件损坏，请检查 time_data.json")
        sys.exit(1)


def save_data(data):
    """保存数据到文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_category(raw):
    """
    解析类别输入
    顺序：精确匹配英文key → 中文全名 → 简写（均不区分大小写）
    返回英文key或None
    """
    raw_lower = raw.lower().strip()
    # 精确匹配英文key
    if raw_lower in CATEGORIES:
        return raw_lower
    # 匹配中文名
    for key, (_, cn, _) in CATEGORIES.items():
        if cn == raw.strip():
            return key
    # 匹配简写
    for key, (_, _, short) in CATEGORIES.items():
        if short != "—" and short == raw.strip():
            return key
    return None


def get_category_display(key):
    """返回类别的 emoji + 中文名"""
    emoji, cn, _ = CATEGORIES[key]
    return f"{emoji}{cn}", emoji


def format_duration(minutes):
    """格式化时长：45m / 2h30m / 2h"""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h{mins:02d}m"


def get_week_range(today=None):
    """获取本周范围（周一到今天）"""
    if today is None:
        today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, today


def get_date_range(days, end_today=True):
    """获取过去N天的日期范围"""
    end = date.today()
    if not end_today:
        end = end - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start, end


def filter_logs_by_date(logs, start_date, end_date):
    """过滤指定日期范围内的记录"""
    result = []
    for log in logs:
        log_date = datetime.fromisoformat(log["ts"]).date()
        if start_date <= log_date <= end_date:
            result.append(log)
    return result


def merge_misc_entries(cat_minutes):
    """将杂项类别合并为一个条目"""
    misc_total = sum(cat_minutes.get(cat, 0) for cat in MISC_CATS)
    result = {k: v for k, v in cat_minutes.items() if k not in MISC_CATS}
    if misc_total > 0:
        result["_misc"] = misc_total
    return result


def build_bar(value, max_value, width=16):
    """构建百分比条"""
    if max_value == 0:
        return "░" * width
    filled = int(width * value / max_value)
    return "█" * filled + "░" * (width - filled)


def cmd_log(args):
    """写入时间记录"""
    cat_key = parse_category(args.category)
    if cat_key is None:
        print(f"✗ 不认识的类别：{args.category}，输入 time_tracker.py cat 查看")
        sys.exit(1)

    try:
        minutes = int(args.minutes)
        if minutes <= 0:
            raise ValueError
    except ValueError:
        print("✗ 分钟数必须是正整数")
        sys.exit(1)

    note = " ".join(args.note) if args.note else ""

    data = load_data()
    now = datetime.now()
    entry = {
        "date": now.strftime("%Y-%m-%d"),
        "cat": cat_key,
        "min": minutes,
        "note": note,
        "ts": now.isoformat(),
    }
    data["logs"].append(entry)
    save_data(data)

    display, _ = get_category_display(cat_key)
    print(f"✓ {display} {format_duration(minutes)} {note}")


def cmd_today(args):
    """当日汇总"""
    data = load_data()
    today_str = date.today().strftime("%Y-%m-%d")

    today_logs = [log for log in data["logs"] if log["date"] == today_str]

    if not today_logs:
        print("今天还没记。time_tracker.py log <类别> <分钟>")
        return

    # 按类别汇总
    cat_minutes = defaultdict(int)
    cat_notes = defaultdict(set)
    for log in today_logs:
        cat_minutes[log["cat"]] += log["min"]
        if log["note"]:
            cat_notes[log["cat"]].add(log["note"])

    # 排序
    sorted_cats = sorted(cat_minutes.items(), key=lambda x: -x[1])

    total_min = sum(cat_minutes.values())
    remaining = 960 - total_min  # 16h清醒时间

    print("──────────────────────")
    print(f"  今日（{today_str}）")
    print("──────────────────────")

    for cat_key, minutes in sorted_cats:
        display, _ = get_category_display(cat_key)
        notes_str = ""
        if cat_notes[cat_key]:
            notes_str = "  " + "，".join(sorted(cat_notes[cat_key]))
        print(f"  {display}  {format_duration(minutes):>6}{notes_str}")

    print("──────────────────────")
    print(f"  已用  {format_duration(total_min)}")
    print(f"  剩余  {format_duration(remaining)}（基于16h清醒）")

    # 作业检查
    if "homework" not in cat_minutes:
        print(f"  🔵 作业  0m")


def _aggregate_week_drain(logs, start_date, end_date, title, subtitle):
    """week 和 drain 的通用聚合逻辑"""
    filtered = filter_logs_by_date(logs, start_date, end_date)

    if not filtered:
        return f"{title.split('（')[0]}还没记任何东西。"

    cat_minutes = defaultdict(int)
    cat_notes = defaultdict(set)
    for log in filtered:
        cat_minutes[log["cat"]] += log["min"]
        if log["note"]:
            cat_notes[log["cat"]].add(log["note"])

    # 杂项合并
    merged = merge_misc_entries(cat_minutes)

    # 排序
    sorted_entries = sorted(merged.items(), key=lambda x: -x[1])

    total_min = sum(merged.values())
    max_min = max(merged.values()) if merged else 0

    lines = []
    lines.append("──────────────────────────────")
    lines.append(f"  {title}")
    lines.append("──────────────────────────────")

    for cat_key, minutes in sorted_entries:
        if cat_key == "_misc":
            display = "⚪杂项"
            emoji = "⚪"
        else:
            display, emoji = get_category_display(cat_key)
        bar = build_bar(minutes, max_min)
        pct = int(100 * minutes / total_min) if total_min > 0 else 0
        extra = " ←" if cat_key == "homework" and minutes == 0 else ""
        lines.append(f"  {display} {format_duration(minutes):>6}  {bar}  {pct:>2}%{extra}")

    lines.append("──────────────────────────────")
    lines.append(f"  合计 {format_duration(total_min)}")

    # 警告
    tutoring_min = cat_minutes.get("tutoring", 0)
    homework_min = cat_minutes.get("homework", 0)

    if tutoring_min > 0 and homework_min == 0:
        lines.append(f"\n  ⚠️ {format_duration(tutoring_min)}上课 vs 0h作业")

    return "\n".join(lines)


def cmd_week(args):
    """本周时间排行"""
    data = load_data()
    monday, today = get_week_range()
    title = f"本周黑洞（{monday.strftime('%m/%d')} ~ {today.strftime('%m/%d')}）"
    result = _aggregate_week_drain(data["logs"], monday, today, title, "")
    print(result)


def cmd_drain(args):
    """过去N天黑洞排行"""
    days = args.days
    data = load_data()
    start, end = get_date_range(days)
    title = f"🕳️ 过去{days}天黑洞（{start.strftime('%m/%d')} ~ {end.strftime('%m/%d')}）"
    result = _aggregate_week_drain(data["logs"], start, end, title, "")
    print(result)


def cmd_gap(args):
    """毕设/作业停滞状态诊断"""
    data = load_data()
    today_date = date.today()
    _, today_end = get_date_range(1)  # 今天
    monday, _ = get_week_range()

    lines = []
    lines.append("──────────────────────")
    lines.append("  ⏰ 学业状态")
    lines.append("──────────────────────")

    for cat_key, label in [("homework", "作业")]:
        cat_logs = [log for log in data["logs"] if log["cat"] == cat_key]

        # 查找最后一次记录
        if not cat_logs:
            status_line = f"  🔵{label}：从没记过"
        else:
            last_log = max(cat_logs, key=lambda x: x["ts"])
            last_date = datetime.fromisoformat(last_log["ts"]).date()
            days_ago = (today_date - last_date).days

            # 本周投入
            week_logs = [log for log in cat_logs if datetime.fromisoformat(log["ts"]).date() >= monday]
            week_min = sum(log["min"] for log in week_logs)

            if days_ago == 0:
                status_line = f"  🔵{label}：今天碰过 ✓"
            else:
                weeks = days_ago // 7
                if days_ago >= 28:
                    severity = "🔴🔴🔴"
                elif days_ago >= 7:
                    severity = f"🔴"
                else:
                    severity = "⚠️"

                week_str = f"（{weeks}周）" if weeks > 0 else ""
                status_line = f"  🔵{label}：已停滞 {days_ago}天{week_str} {severity}"
                status_line += f"\n     本周投入：{format_duration(week_min)}"

        lines.append(status_line)

    print("\n".join(lines))


def cmd_cat(args):
    """列出所有类别"""
    print("类别表：")
    for key, (emoji, cn, short) in CATEGORIES.items():
        short_str = f"  简写：{short}" if short != "—" else ""
        print(f"  {emoji}{cn}   {key}   {short_str}".rstrip())


def main():
    parser = argparse.ArgumentParser(description="时间黑洞追踪器")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # log 命令
    log_parser = subparsers.add_parser("log", help="写入时间记录")
    log_parser.add_argument("category", help="类别")
    log_parser.add_argument("minutes", help="分钟数")
    log_parser.add_argument("note", nargs="*", help="备注")

    # today 命令
    subparsers.add_parser("today", help="当日汇总")

    # week 命令
    subparsers.add_parser("week", help="本周排行")

    # gap 命令
    subparsers.add_parser("gap", help="停滞状态诊断")

    # cat 命令
    subparsers.add_parser("cat", help="列出类别")

    # drain 命令
    drain_parser = subparsers.add_parser("drain", help="过去N天黑洞排行")
    drain_parser.add_argument("--days", type=int, default=7, help="回溯天数")

    args = parser.parse_args()

    commands = {
        "log": cmd_log,
        "today": cmd_today,
        "week": cmd_week,
        "gap": cmd_gap,
        "cat": cmd_cat,
        "drain": cmd_drain,
    }

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command not in commands:
        print(f"未知命令：{args.command}")
        print("可用命令：log, today, week, gap, cat, drain")
        sys.exit(1)

    commands[args.command](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简日记系统 - 一句话记录
依赖：仅标准库 (json, sys, os, datetime, argparse)
"""

import json
import sys
import os
import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal_data.json")
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory")
WIDTH = 25


# ============== 数据层 ==============

def load_data():
    """读取数据文件，不存在视为空，损坏则报错退出"""
    if not os.path.exists(DATA_FILE):
        return {"entries": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "entries" not in data or not isinstance(data["entries"], list):
            raise ValueError("Invalid structure")
        return data
    except (json.JSONDecodeError, ValueError, IOError):
        print("✗ 数据文件损坏，请检查 journal_data.json")
        sys.exit(1)


def save_data(entries):
    """保存数据文件，并同步到 memory/目录的每日笔记"""
    # 保存 JSON
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)
    
    # 同步到 memory/目录
    sync_to_memory(entries)


def sync_to_memory(entries):
    """将今天的条目同步到 memory/YYYY-MM-DD.md"""
    today = get_today_str()
    today_entries = [e for e in entries if e["date"] == today]
    
    if not today_entries:
        return
    
    # 确保 memory 目录存在
    os.makedirs(MEMORY_DIR, exist_ok=True)
    memory_file = os.path.join(MEMORY_DIR, f"{today}.md")
    
    # 读取现有内容（如果有）
    existing_content = ""
    if os.path.exists(memory_file):
        with open(memory_file, "r", encoding="utf-8") as f:
            existing_content = f.read()
    
    # 生成日记部分
    diary_section = "# 📔 今日日记\n\n"
    for e in sorted(today_entries, key=lambda x: x["ts"]):
        ts_display = format_ts_full(e["ts"])
        diary_section += f"- [{ts_display}] {e['text']}\n"
    diary_section += "\n"
    
    # 如果已有日记部分，替换；否则追加
    if "# 📔 今日日记\n" in existing_content:
        # 替换现有日记部分
        lines = existing_content.split("\n")
        new_lines = []
        in_diary_section = False
        skip_until_next_header = False
        
        for line in lines:
            if line.strip() == "# 📔 今日日记":
                in_diary_section = True
                skip_until_next_header = True
                new_lines.append("# 📔 今日日记")
                continue
            
            if skip_until_next_header:
                if line.startswith("# ") and line != "# 📔 今日日记":
                    skip_until_next_header = False
                    new_lines.append("")
                    new_lines.append(diary_section.rstrip())
                    new_lines.append("")
                    new_lines.append(line)
                continue
            else:
                new_lines.append(line)
        
        if skip_until_next_header:
            new_lines.append("")
            new_lines.append(diary_section.rstrip())
        
        content = "\n".join(new_lines)
    else:
        content = existing_content + diary_section
    
    with open(memory_file, "w", encoding="utf-8") as f:
        f.write(content)


# ============== 工具函数 ==============

def get_today_str():
    return datetime.date.today().isoformat()


def get_week_start():
    """返回本周一日期字符串"""
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.isoformat()


def format_ts(ts_str):
    """将 ISO ts 转为 M/D HH:MM 格式"""
    dt = datetime.datetime.fromisoformat(ts_str)
    return f"{dt.month}/{dt.day} {dt.hour:02d}:{dt.minute:02d}"


def format_ts_full(ts_str):
    """将 ISO ts 转为 YYYY-MM-DD HH:MM 格式"""
    dt = datetime.datetime.fromisoformat(ts_str)
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"


def print_box(lines):
    """打印框线格式输出"""
    print("┌" + "─" * WIDTH + "┐")
    for line in lines:
        print(f"│ {line:<{WIDTH - 1}} │")
    print("└" + "─" * WIDTH + "┘")


def print_header(title):
    """打印居中标题栏"""
    print("┌" + "─" * WIDTH + "┐")
    print(f"│ {title:^{WIDTH - 1}} │")
    print("└" + "─" * WIDTH + "┘")


# ============== 业务逻辑 ==============

def add_entry(text):
    """创建新日记条目"""
    now = datetime.datetime.now()
    return {
        "date": now.date().isoformat(),
        "text": text,
        "ts": now.isoformat()
    }


def get_today_entries(entries):
    """获取今天的所有条目"""
    today = get_today_str()
    return [e for e in entries if e["date"] == today]


def get_week_entries(entries):
    """获取本周一至今的所有条目"""
    monday = get_week_start()
    today = get_today_str()
    return [e for e in entries if monday <= e["date"] <= today]


def get_recent_entries(entries, n=10):
    """获取最近N条条目，按时间倒序"""
    sorted_entries = sorted(entries, key=lambda x: x["ts"], reverse=True)
    return sorted_entries[:n]


def search_entries(entries, keywords):
    """多关键词AND搜索"""
    results = []
    for e in entries:
        text_lower = e["text"].lower()
        if all(kw.lower() in text_lower for kw in keywords):
            results.append(e)
    return results


# ============== 命令处理器 ==============

def cmd_write(text):
    """写日记：有参数时添加新条目"""
    data = load_data()
    entry = add_entry(text)
    data["entries"].append(entry)
    save_data(data["entries"])
    print(f"✓ {format_ts_full(entry['ts'])} — {entry['text']}")


def cmd_today():
    """无参数：查看今天的所有条目"""
    data = load_data()
    today_entries = get_today_entries(data["entries"])

    if not today_entries:
        print("今天还没写日记。journal.py \"一句话\"")
        return

    # 按时间正序排列
    today_entries.sort(key=lambda x: x["ts"])

    print("──────────────────────────")
    print(f"  📔 {get_today_str()}")
    print("──────────────────────────")
    for e in today_entries:
        ts_short = format_ts(e["ts"])
        # 简单换行处理
        lines = wrap_text(e["text"], width=20)
        print(f"  {ts_short}  {lines[0]}")
        for line in lines[1:]:
            print(f"         {line}")
    print("──────────────────────────")
    print(f"  共{len(today_entries)}条")


def cmd_week():
    """本周回顾：周一到今天，按日期分组"""
    data = load_data()
    monday = get_week_start()
    today = get_today_str()

    # 生成本周所有日期
    monday_date = datetime.date.fromisoformat(monday)
    today_date = datetime.date.fromisoformat(today)
    all_dates = []
    d = monday_date
    while d <= today_date:
        all_dates.append(d.isoformat())
        d += datetime.timedelta(days=1)

    # 按日期分组
    entries_by_date = {}
    for e in data["entries"]:
        if e["date"] in all_dates:
            if e["date"] not in entries_by_date:
                entries_by_date[e["date"]] = []
            entries_by_date[e["date"]].append(e)

    # 计算统计
    days_with_records = len(entries_by_date)
    total_days = len(all_dates)
    total_entries = sum(len(v) for v in entries_by_date.values())

    # 打印标题
    monday_display = f"{monday_date.month}/{monday_date.day}"
    today_display = f"{today_date.month}/{today_date.day}"
    print("──────────────────────────")
    print(f"  📔 本周日记（{monday_display} ~ {today_display}）")
    print("──────────────────────────")

    # 逐天打印
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i, d in enumerate(all_dates):
        date_obj = datetime.date.fromisoformat(d)
        day_name = weekday_names[date_obj.weekday()]
        day_display = f"{date_obj.month}/{date_obj.day}"

        if d in entries_by_date:
            print(f"  {day_name} {day_display}")
            entries = sorted(entries_by_date[d], key=lambda x: x["ts"])
            for e in entries:
                ts_short = format_ts(e["ts"])
                lines = wrap_text(e["text"], width=20)
                print(f"    {ts_short}  {lines[0]}")
                for line in lines[1:]:
                    print(f"    {'':8}{line}")
        else:
            print(f"  {day_name} {day_display}")
            print(f"    （无记录）")

    print("──────────────────────────")
    print(f"  共{total_entries}条 | {days_with_records}天有记录 | {total_days - days_with_records}天无记录")


def cmd_last(n=10):
    """最近N条日记"""
    data = load_data()
    recent = get_recent_entries(data["entries"], n)

    if not recent:
        print("暂无日记记录。")
        return

    print("──────────────────────────")
    print(f"  📔 最近{len(recent)}条")
    print("──────────────────────────")
    for e in recent:
        ts_short = format_ts(e["ts"])
        lines = wrap_text(e["text"], width=20)
        print(f"  {ts_short}  {lines[0]}")
        for line in lines[1:]:
            print(f"         {line}")
    print("──────────────────────────")


def cmd_search(keywords):
    """搜索日记"""
    data = load_data()
    results = search_entries(data["entries"], keywords)

    if not results:
        keyword_str = " ".join(keywords)
        print(f"未找到匹配 \"{keyword_str}\" 的记录")
        return

    print("──────────────────────────")
    print(f"  🔍 搜索 \"{' '.join(keywords)}\"")
    print("──────────────────────────")
    for e in results:
        ts_short = format_ts(e["ts"])
        lines = wrap_text(e["text"], width=20)
        print(f"  {ts_short}  {lines[0]}")
        for line in lines[1:]:
            print(f"         {line}")
    print("──────────────────────────")
    print(f"  共{len(results)}条")


def cmd_help():
    """未知命令：列出可用命令"""
    print("可用命令：")
    print("  journal.py [text]   - 写日记 / 查看今日")
    print("  journal.py week     - 本周回顾")
    print("  journal.py last [N] - 最近N条（默认10）")
    print("  journal.py search <关键词...> - 搜索")
    sys.exit(1)


def wrap_text(text, width=20):
    """简单文本换行"""
    if len(text) <= width:
        return [text]
    lines = []
    words = text.split()
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [text]


# ============== 主入口 ==============

def main():
    if len(sys.argv) == 1:
        cmd_today()
    elif sys.argv[1] == "week":
        cmd_week()
    elif sys.argv[1] == "last":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cmd_last(n)
    elif sys.argv[1] == "search":
        if len(sys.argv) < 3:
            print("搜索需要关键词。")
            sys.exit(1)
        cmd_search(sys.argv[2:])
    else:
        # 写日记模式
        cmd_write(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()

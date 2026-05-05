#!/usr/bin/env python3
"""
capture — 1秒捕获杂念
用法: python capture.py "脑子里冒出的任何事"
"""
import re
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# 直接操作灵犀 inbox 文件，不引入模块路径问题
INBOX = Path(__file__).parent / "灵犀" / "data" / "inbox.json"


def load_inbox():
    import json
    if not INBOX.exists():
        return []
    with open(INBOX, "r", encoding="utf-8") as f:
        return json.load(f)


def save_inbox(items):
    import json
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with open(INBOX, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def uuid8():
    import uuid
    return str(uuid.uuid4())[:8]


def parse_content(raw: str) -> dict:
    """从内容中自动提取 deadline / person / project，返回 item dict"""
    content = raw.strip()
    item = {
        "type": "task",
        "content": content,
        "from_source": "",
        "urgency": 3,
        "deadline": None,
        "effort": "medium",
        "tags": [],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "deferred_to": None,
        "waiting_for": None,
        "context": "anytask",
        "id": uuid8(),
    }

    # 提取截止时间
    deadline = None
    m = re.search(r"截止?\s*(\d+[日号])", content)
    if m:
        day = re.sub(r"\D", "", m.group(1))
        deadline = (datetime.now() + timedelta(days=int(day))).strftime("%Y-%m-%d")
    elif re.search(r"今天", content):
        deadline = datetime.now().strftime("%Y-%m-%d")
    elif re.search(r"明天", content):
        deadline = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif re.search(r"后天", content):
        deadline = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    elif re.search(r"这周", content):
        days_left = 7 - datetime.now().weekday()
        deadline = (datetime.now() + timedelta(days=days_left)).strftime("%Y-%m-%d")
    if deadline:
        item["deadline"] = deadline
        item["content"] = re.sub(r"截止?\s*\d+[日号]|今天|明天|后天|这周", "", content).strip()

    # 提取来源/人
    person_map = {
        "导师": "导师", "导师说": "导师", "导师问": "导师",
        "慧美": "女友", "慧美说": "女友", "慧美问": "女友",
        "罗晟宇": "学生", "罗晟宇妈": "家长", "郑皓轩": "学生",
        "皓轩": "学生", "晟宇": "学生",
    }
    for kw, source in person_map.items():
        if kw in content:
            item["from_source"] = source
            # 导师/慧美说的话 → 默认是等待回复
            if source in ("导师", "女友") and "说" in content:
                item["type"] = "waiting"
                item["waiting_for"] = source
            break

    # 提取等待
    wait_map = {
        "等导师": "导师", "等慧美": "女友", "等回复": "对方",
        "等罗晟宇": "学生", "等皓轩": "学生",
    }
    for kw, waiting_for in wait_map.items():
        if kw in content:
            item["type"] = "waiting"
            item["waiting_for"] = waiting_for
            break

    # 提取想买
    buy_keywords = ["想买", "想买", "要不要买", "可以买吗"]
    for kw in buy_keywords:
        if kw in content:
            item["type"] = "want"
            break

    # 自动打 tag
    tag_map = {
        "毕设": "毕设", "论文": "毕设", "仿真": "毕设",
        "家教": "家教", "学生": "家教", "上课": "家教", "备课": "家教",
        "推文": "自媒体", "公众号": "自媒体", "漫剧": "自媒体", "视频": "自媒体",
        "体检": "健康", "医院": "健康", "心脏": "健康",
        "钱": "财务", "预算": "财务", "花": "财务",
        "慧美": "关系", "吵架": "关系", "搬出去": "关系",
    }
    for kw, tag in tag_map.items():
        if kw in content:
            if tag not in item["tags"]:
                item["tags"].append(tag)

    # 清理内容
    item["content"] = re.sub(r"\s+", " ", item["content"]).strip("，、。 ")

    return item


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("capture — 1秒捕获杂念")
        print("用法: python capture.py \"脑子里冒出的任何事\"")
        print("示例: python capture.py \"导师说下周要开会\"")
        print("      python capture.py \"想买机械键盘 799块\"")
        print("      python capture.py \"明天要给皓轩备课\"")
        return

    raw = " ".join(sys.argv[1:])
    item = parse_content(raw)
    items = load_inbox()
    items.append(item)
    save_inbox(items)

    # 打印结果
    type_icon = {"task": "📋", "waiting": "⏳", "want": "🛒"}.get(item["type"], "•")
    deadline_str = f" 截止{item['deadline']}" if item["deadline"] else ""
    tags_str = f" [{','.join(item['tags'])}]" if item["tags"] else ""
    source_str = f" @{item['from_source']}" if item["from_source"] else ""

    print(f"✅ {type_icon} {item['content']}{source_str}{tags_str}{deadline_str}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except FileNotFoundError as e:
        print(f"\n⛔ 文件未找到：{e}")
        print("💡 下一步：检查 capture.json 数据文件是否存在")
        sys.exit(1)
    except Exception as e:
        print(f"\n⛔ {type(e).__name__}: {e}")
        print("💡 下一步：检查参数或运行 `python capture.py --help`")
        sys.exit(1)

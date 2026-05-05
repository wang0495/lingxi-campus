#!/usr/bin/env python3
"""
灵犀 · 统一待办与信息管理系统
Unified Inbox for Tasks, Messages, Wants, References, and Waiting items.
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

from core.item import Item, ItemType, ItemStatus, new_item
from core.priority import calc_priority, sort_by_priority
from core import storage


def format_item(item: Item, index: int) -> str:
    """Format an item for display."""
    score = calc_priority(item)

    # Type emoji
    type_emoji = {
        ItemType.TASK: "📋",
        ItemType.MESSAGE: "💬",
        ItemType.WANT: "🛒",
        ItemType.REFERENCE: "📎",
        ItemType.WAITING: "⏳",
    }
    emoji = type_emoji.get(item.type, "•")

    # Deadline display
    deadline_str = ""
    if item.deadline:
        try:
            deadline_dt = datetime.fromisoformat(item.deadline.replace('年', '-').replace('月', '-').replace('日', ''))
            now = datetime.now()
            hours_left = (deadline_dt - now).total_seconds() / 3600
            if hours_left < 0:
                deadline_str = f" ⚠️已过期"
            elif hours_left < 24:
                deadline_str = f" ⚠️截止今晚"
            elif hours_left < 48:
                deadline_str = f" 截止明天"
            else:
                deadline_str = f" 截止{item.deadline}"
        except (ValueError, AttributeError):
            deadline_str = f" 截止{item.deadline}"

    # Waiting info
    waiting_str = ""
    if item.type == ItemType.WAITING and item.waiting_for:
        days_waiting = (datetime.now() - datetime.fromisoformat(item.created_at)).days
        waiting_str = f" 等了{days_waiting}天"

    # Tags
    tags_str = ""
    if item.tags:
        tags_str = f" [{','.join(item.tags)}]"

    # Source
    source_str = f" @{item.from_source}" if item.from_source else ""

    return f"  {index}. {emoji} {item.content}{source_str}{tags_str}{deadline_str}{waiting_str} [优先级:{score}]"


def cmd_inbox(args):
    """Display pending items sorted by priority."""
    items = storage.get_pending_items()
    items = sort_by_priority(items)

    if not items:
        print("📮 灵犀 · 收件箱为空")
        print("   使用 `python lingxi.py add \"内容\"` 添加待办")
        return

    print(f"📮 灵犀 · 待处理 {len(items)} 条")
    print("-" * 60)
    for i, item in enumerate(items, 1):
        print(format_item(item, i))
    print("-" * 60)


def cmd_add(args):
    """Add a new item to inbox."""
    tags = args.tag if args.tag else []
    if args.tags:
        tags = args.tags.split(',')

    item = new_item(
        content=args.content,
        item_type=ItemType.TASK,
        from_source=args.from_source or "",
        deadline=args.deadline,
        tags=tags,
        effort=args.effort or "medium",
    )

    storage.add_item(item)
    print(f"✅ 已添加: {args.content}")


def cmd_do(args):
    """Mark item as done by index."""
    item = storage.get_item_by_index(args.index)
    if not item:
        print(f"❌ 未找到第 {args.index} 条")
        return

    item.status = ItemStatus.DONE
    storage.update_item(item.id, {"status": ItemStatus.DONE})
    print(f"✅ 已完成: {item.content}")


def cmd_defer(args):
    """Defer item to a later time."""
    item = storage.get_item_by_index(args.index)
    if not item:
        print(f"❌ 未找到第 {args.index} 条")
        return

    item.status = ItemStatus.DEFERRED
    item.deferred_to = args.defer_to
    storage.update_item(item.id, {
        "status": ItemStatus.DEFERRED,
        "deferred_to": args.defer_to
    })
    print(f"⏰ 已推迟到: {args.defer_to}")


def cmd_archive(args):
    """Archive an item."""
    item = storage.get_item_by_index(args.index)
    if not item:
        print(f"❌ 未找到第 {args.index} 条")
        return

    item.status = ItemStatus.ARCHIVED
    storage.update_item(item.id, {"status": ItemStatus.ARCHIVED})
    print(f"📁 已归档: {item.content}")


def cmd_msg(args):
    """Add a message-type item (waiting for reply)."""
    tags = args.tag if args.tag else []
    if args.tags:
        tags = args.tags.split(',')

    item = new_item(
        content=args.content,
        item_type=ItemType.MESSAGE,
        from_source=args.from_source or "",
        waiting_for=args.waiting,
        tags=tags,
    )

    storage.add_item(item)
    print(f"💬 已添加消息: {args.content} (等待 {args.waiting})")


def cmd_want(args):
    """Add a want-type item (something you want to buy)."""
    tags = args.tag if args.tag else []
    if args.tags:
        tags = args.tags.split(',')

    content = args.content
    if args.price:
        content = f"{args.content} ¥{args.price}"
    if args.reason:
        content = f"{content} - {args.reason}"

    item = new_item(
        content=content,
        item_type=ItemType.WANT,
        from_source=args.from_source or "",
        tags=tags,
    )

    storage.add_item(item)
    print(f"🛒 已添加想买: {args.content}")


def cmd_waiting(args):
    """Add a waiting-type item (waiting for external result)."""
    tags = args.tag if args.tag else []
    if args.tags:
        tags = args.tags.split(',')

    item = new_item(
        content=args.content,
        item_type=ItemType.WAITING,
        from_source=args.from_source or "",
        waiting_for=args.waiting_for,
        tags=tags,
    )

    storage.add_item(item)
    print(f"⏳ 已添加等待: {args.content} (等待 {args.waiting_for})")


def cmd_today(args):
    """Show items due today."""
    items = storage.get_pending_items()
    today = datetime.now().date()

    today_items = []
    for item in items:
        if item.deadline:
            try:
                deadline = datetime.fromisoformat(item.deadline.replace('年', '-').replace('月', '-').replace('日', ''))
                if deadline.date() == today:
                    today_items.append(item)
            except (ValueError, AttributeError):
                pass

    if not today_items:
        print("📅 今天没有截止的任务")
        return

    today_items = sort_by_priority(today_items)
    print(f"📅 今日截止 {len(today_items)} 条")
    print("-" * 60)
    for i, item in enumerate(today_items, 1):
        print(format_item(item, i))
    print("-" * 60)


def cmd_next(args):
    """Show the highest priority item."""
    items = storage.get_pending_items()
    if not items:
        print("📮 收件箱为空")
        return

    items = sort_by_priority(items)
    top = items[0]
    print("🔝 下一件最重要的事:")
    print(format_item(top, 1))


def cmd_review(args):
    """Review all pending items one by one."""
    items = storage.get_pending_items()
    items = sort_by_priority(items)

    if not items:
        print("📮 收件箱为空，无需 review")
        return

    print(f"📮 开始 review，共 {len(items)} 条")
    print("-" * 60)

    for i, item in enumerate(items, 1):
        print(format_item(item, i))
        print(f"   操作: do {i} / defer {i} <时间> / archive {i} / skip")
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出 review")
            break

        if cmd.startswith('do'):
            storage.update_item(item.id, {"status": ItemStatus.DONE})
            print(f"   ✅ 已完成")
        elif cmd.startswith('defer'):
            parts = cmd.split()
            if len(parts) >= 2:
                defer_to = ' '.join(parts[1:])
                storage.update_item(item.id, {
                    "status": ItemStatus.DEFERRED,
                    "deferred_to": defer_to
                })
                print(f"   ⏰ 已推迟到 {defer_to}")
        elif cmd.startswith('archive'):
            storage.update_item(item.id, {"status": ItemStatus.ARCHIVED})
            print(f"   📁 已归档")
        else:
            print(f"   ⏭️ 跳过")

        print()

    print("📮 Review 完成!")


def cmd_clear(args):
    """Clear all done items."""
    items = storage.load_items()
    done_count = sum(1 for i in items if i.status == ItemStatus.DONE)
    storage.clear_done()
    print(f"🗑️ 已清空 {done_count} 条已完成项")


def parse_date_relative(date_str: str) -> Optional[str]:
    """Parse relative date strings like '明天', '后天', '下周'."""
    now = datetime.now()

    if '明天' in date_str:
        target = now + timedelta(days=1)
        # Try to extract time
        if '点' in date_str:
            try:
                hour = int(''.join(filter(str.isdigit, date_str.split('点')[0][-2:])))
                target = target.replace(hour=hour, minute=0, second=0)
            except:
                pass
        return target.isoformat()

    if '后天' in date_str:
        target = now + timedelta(days=2)
        return target.isoformat()

    if '下周' in date_str:
        target = now + timedelta(weeks=1)
        return target.isoformat()

    # Try direct ISO format
    try:
        datetime.fromisoformat(date_str)
        return date_str
    except:
        pass

    return None


def main():
    parser = argparse.ArgumentParser(
        description="灵犀 · 统一待办与信息管理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # inbox
    subparsers.add_parser("inbox", help="查看收件箱")

    # add
    add_parser = subparsers.add_parser("add", help="添加新任务")
    add_parser.add_argument("content", help="任务内容")
    add_parser.add_argument("--from", dest="from_source", default="", help="来源")
    add_parser.add_argument("--deadline", dest="deadline", help="截止时间")
    add_parser.add_argument("--tag", dest="tag", action="append", help="标签")
    add_parser.add_argument("--tags", dest="tags", help="标签(逗号分隔)")
    add_parser.add_argument("--effort", dest="effort", choices=["small", "medium", "large"], default="medium")

    # do
    do_parser = subparsers.add_parser("do", help="完成任务")
    do_parser.add_argument("index", type=int, help="任务序号")

    # defer
    defer_parser = subparsers.add_parser("defer", help="推迟任务")
    defer_parser.add_argument("index", type=int, help="任务序号")
    defer_parser.add_argument("defer_to", help="推迟到")

    # archive
    archive_parser = subparsers.add_parser("archive", help="归档任务")
    archive_parser.add_argument("index", type=int, help="任务序号")

    # msg
    msg_parser = subparsers.add_parser("msg", help="添加待处理消息")
    msg_parser.add_argument("content", help="消息内容")
    msg_parser.add_argument("--from", dest="from_source", default="", help="来自谁")
    msg_parser.add_argument("--waiting", dest="waiting", required=True, help="等待谁回复")
    msg_parser.add_argument("--tag", dest="tag", action="append", help="标签")
    msg_parser.add_argument("--tags", dest="tags", help="标签(逗号分隔)")

    # want
    want_parser = subparsers.add_parser("want", help="添加想买的东西")
    want_parser.add_argument("content", help="想买的东西")
    want_parser.add_argument("--from", dest="from_source", default="", help="来源")
    want_parser.add_argument("--price", dest="price", type=int, help="价格")
    want_parser.add_argument("--reason", dest="reason", help="购买原因")
    want_parser.add_argument("--tag", dest="tag", action="append", help="标签")
    want_parser.add_argument("--tags", dest="tags", help="标签(逗号分隔)")

    # waiting
    waiting_parser = subparsers.add_parser("waiting", help="添加等待项")
    waiting_parser.add_argument("content", help="等待事项")
    waiting_parser.add_argument("--from", dest="from_source", default="", help="来源")
    waiting_parser.add_argument("--waiting_for", dest="waiting_for", required=True, help="等谁/等什么")
    waiting_parser.add_argument("--tag", dest="tag", action="append", help="标签")
    waiting_parser.add_argument("--tags", dest="tags", help="标签(逗号分隔)")

    # today
    subparsers.add_parser("today", help="今日截止")

    # next
    subparsers.add_parser("next", help="下一件最重要的事")

    # review
    subparsers.add_parser("review", help="逐条 review")

    # clear
    subparsers.add_parser("clear", help="清空已完成")

    args = parser.parse_args()

    if not args.command:
        # Default to inbox
        cmd_inbox(args)
        return

    # Process relative dates
    if hasattr(args, 'deadline') and args.deadline:
        parsed = parse_date_relative(args.deadline)
        if parsed:
            args.deadline = parsed

    # Route commands
    commands = {
        "inbox": cmd_inbox,
        "add": cmd_add,
        "do": cmd_do,
        "defer": cmd_defer,
        "archive": cmd_archive,
        "msg": cmd_msg,
        "want": cmd_want,
        "waiting": cmd_waiting,
        "today": cmd_today,
        "next": cmd_next,
        "review": cmd_review,
        "clear": cmd_clear,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd(args)
    else:
        print(f"未知命令: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

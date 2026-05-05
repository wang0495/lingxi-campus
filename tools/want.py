#!/usr/bin/env python3
"""
want - 时间预购工具
把"要不要买"的判断，变成"做还是不做"的否决
"""
import argparse
import sys

from commands.add import add
from commands.list import list_all
from commands.check import check
from commands.approve import approve
from commands.drop import drop
from commands.week import week
from commands.budget import budget


def main():
    # 如果没有任何参数，显示帮助
    if len(sys.argv) == 1:
        print("want - 时间预购工具，把'要不要买'变成'做还是不做'\n")
        print("用法:")
        print("  want <物品名>                    添加欲望")
        print("  want <物品名> --price <价格>     添加带价格的欲望")
        print("  want list                        列出所有欲望")
        print("  want check                       到期检查")
        print("  want approve <id>                确认购买")
        print("  want drop <id>                  丢弃欲望")
        print("  want week <id>                   推迟一周")
        print("  want budget                      预算检查")
        return

    first_arg = sys.argv[1]

    # 如果第一个参数是子命令，走 subparsers
    subcommands = ["add", "list", "check", "approve", "drop", "week", "budget"]
    if first_arg in subcommands:
        parser = argparse.ArgumentParser(
            description="want - 时间预购工具，把'要不要买'变成'做还是不做'"
        )
        subparsers = parser.add_subparsers(dest="command", help="子命令")

        add_parser = subparsers.add_parser("add", help="添加欲望")
        add_parser.add_argument("item", help="物品名称")
        add_parser.add_argument("--price", "-p", type=int, default=0, help="价格")
        add_parser.add_argument("--reason", "-r", default="", help="购买原因")

        subparsers.add_parser("list", help="列出所有欲望")
        subparsers.add_parser("check", help="到期检查")

        approve_parser = subparsers.add_parser("approve", help="确认购买")
        approve_parser.add_argument("id", type=int, help="欲望 ID")

        drop_parser = subparsers.add_parser("drop", help="丢弃欲望")
        drop_parser.add_argument("id", type=int, help="欲望 ID")

        week_parser = subparsers.add_parser("week", help="推迟一周")
        week_parser.add_argument("id", type=int, help="欲望 ID")

        subparsers.add_parser("budget", help="预算检查")

        args = parser.parse_args()

        if args.command == "add":
            add(args.item, args.price, args.reason)
        elif args.command == "list":
            list_all()
        elif args.command == "check":
            check()
        elif args.command == "approve":
            approve(args.id)
        elif args.command == "drop":
            drop(args.id)
        elif args.command == "week":
            week(args.id)
        elif args.command == "budget":
            budget()
        else:
            parser.print_help()
    else:
        # 直接传物品名，当作 add 处理
        item = first_arg
        price = 0
        reason = ""

        i = 2
        while i < len(sys.argv):
            if sys.argv[i] in ("--price", "-p"):
                price = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 0
                i += 2
            elif sys.argv[i] in ("--reason", "-r"):
                reason = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
                i += 2
            else:
                i += 1

        add(item, price, reason)


if __name__ == "__main__":
    main()

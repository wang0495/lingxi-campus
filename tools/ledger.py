# -*- coding: utf-8 -*-
"""
简易记账工具（双轨版）
两条线分开：
  现金流：记录真实银行账户进出
  预算池：上月收入覆盖本月支出

用法：
  python ledger.py log <字符串>          # 一句话记账，自动分类（例：log "43.56 卫生巾 交通费1元"）
  python ledger.py income <金额> --source <来源> [--note <备注>] [--date YYYY-MM-DD] [--budget-month YYYY-MM]
  python ledger.py expense <金额> --category <类别> [--note <备注>] [--date YYYY-MM-DD] [--budget-month YYYY-MM> [--once] [--yes]

  ⚠️ 位置参数（金额）必须写在选项前面！
  ✅ 正确：expense 6.9 --category 餐饮 --note 午饭
  ❌ 错误：expense --category 餐饮 --note 午饭 6.9
  python ledger.py modify -k <关键字> --set-category <类别> [--yes]  # 批量修改（默认预览，需 --yes 写入）
  python ledger.py migrate [--yes]             # 迁移旧数据（默认预览，需 --yes 写入）
  python ledger.py today                  # 今日账单
  python ledger.py summary [--month YYYY-MM]
  python ledger.py export
  python ledger.py calc-ladder [--year YYYY-MM] [--show-tiers]
  python ledger.py migrate   # 迁移旧数据，补充 budget_month 字段
  python ledger.py budget-check [--month YYYY-MM]  # 预算执行检查（超支预警）
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime, date
from calendar import monthrange

# 确保 Windows 控制台输出中文不乱码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 数据文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "ledger_data.json")

# 支出类别与收入来源白名单
EXPENSE_CATEGORIES = [
    "餐饮", "零食水果", "交通", "日用杂费", "应急备用金", "固定开支",
    "犒劳", "自我投资", "社交基金", "家人", "其他",
]
INCOME_SOURCES = ["平台", "星火", "私域", "75h线上", "家人", "补贴", "其他"]

# 共同账户类别：支出时自动按 68.7% / 31.3% 分摊
# 映射关系：budget_plan.json 中的分类 -> ledger 类别
SHARED_CATEGORIES = ["餐饮", "零食水果", "交通", "日用杂费", "应急备用金", "房租", "水电杂费"]
# 个人支出类别：不参与分账
PERSONAL_CATEGORIES = ["犒劳", "自我投资", "社交基金", "家人", "生存"]

# 分账比例
USER_RATIO = 0.687
GIRLFRIEND_RATIO = 0.313

# budget_plan.json 路径
BUDGET_PLAN_FILE = os.path.join(SCRIPT_DIR, "..", "finance", "budget_plan.json")

# ──────────────────── 数据读写 ────────────────────

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"records": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    """写入前滚动备份（3份），写完验证完整性，失败自动回滚"""
    # 备份
    backups = [DATA_FILE + ".bak", DATA_FILE + ".bak.bak2"]
    # 只对已存在的文件做备份
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, backups[0])
        if os.path.exists(backups[0]):
            shutil.move(backups[0], backups[1])

    # 写入
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 验证
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            verify = json.load(f)
        if "records" not in verify:
            raise RuntimeError("records 字段缺失")
    except Exception:
        # 回滚
        src = backups[1] if os.path.exists(backups[1]) else backups[0]
        if os.path.exists(src):
            shutil.copy2(src, DATA_FILE)
        raise RuntimeError("写入后验证失败，已自动回滚到备份！")


def load_budget_plan():
    """加载预算计划文件"""
    path = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "finance", "budget_plan.json"))
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_daily_plan(final_date):
    """根据日期获取当日计划金额（仅餐饮）"""
    bp = load_budget_plan()
    if not bp:
        return None
    # 日期格式: 2026-04-01 -> 04-01
    day_key = final_date[5:]  # "04-01"
    # 动态查找月份计划key：尝试 daily_plan_04 / daily_plan_4 / daily_plan_april 等
    month_num = final_date[5:7]  # "04"
    month_name_map = {
        "01": "january", "02": "february", "03": "march", "04": "april",
        "05": "may", "06": "june", "07": "july", "08": "august",
        "09": "september", "10": "october", "11": "november", "12": "december"
    }
    candidates = [
        f"daily_plan_{month_num}",          # daily_plan_04
        f"daily_plan_{month_num.lstrip('0')}",  # daily_plan_4
        f"daily_plan_{month_name_map.get(month_num, '')}",  # daily_plan_april
    ]
    for key in candidates:
        if key in bp:
            daily = bp[key].get(day_key)
            if daily:
                return daily.get("food_budget")
            return None  # key存在但日期不在里面
    return None


def add_record(rtype, amount, category, note="", record_date=None,
               budget_month=None, is_once=False, is_balance=False,
               is_personal=False):
    """添加一条记录

    Args:
        record_date : str  实际发生日期，默认今天
        budget_month: str  归属预算月份，默认：
                          - 收入 → record_date 的下个月
                          - 支出 → record_date 的当月
        is_once     : bool 一次性收支，不参与日均计算
        is_balance  : bool 期初余额标记（存量资产，不计入收入）
        is_personal : bool 个人支出（不参与分账）
    """
    # 日期校验
    if record_date:
        try:
            datetime.strptime(record_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式错误：「{record_date}」，应为 YYYY-MM-DD")
        final_date = record_date
    else:
        final_date = date.today().isoformat()

    # 自动推断 budget_month
    if budget_month is None:
        d = date.fromisoformat(final_date)
        if rtype == "income":
            # 收入归属当月预算池（双轨制：预算=当月实际收入）
            budget_month = f"{d.year}-{d.month:02d}"
        else:
            # 支出归属当月预算池
            budget_month = f"{d.year}-{d.month:02d}"

    data = load_data()
    # 兜底：若 records 字段损坏，保证能继续
    if "records" not in data:
        data["records"] = []
    record = {
        "date": final_date,
        "type": rtype,
        "amount": float(amount),
        "category": category,
        "note": note,
        "budget_month": budget_month,
        "is_once": is_once,
        "is_balance": is_balance,
    }

    # 共同账户自动分账（支出 + 非个人 + 共同类别）
    if rtype == "expense" and not is_personal and category in SHARED_CATEGORIES:
        record["user_share"] = round(float(amount) * USER_RATIO, 2)
        record["girlfriend_share"] = round(float(amount) * GIRLFRIEND_RATIO, 2)

    # 餐饮自动填充 planned_amount
    if rtype == "expense" and category == "餐饮":
        planned = get_daily_plan(final_date)
        if planned is not None:
            record["planned_amount"] = planned

    data["records"].append(record)
    save_data(data)
    return record


# ──────────────────── 数据迁移 ────────────────────

def cmd_migrate(args):
    """迁移旧数据：为所有记录补充 budget_month 字段（不写盘，仅展示变更预览）"""
    data = load_data()
    updated = []
    unchanged = []
    for r in data["records"]:
        if "budget_month" in r:
            unchanged.append(r)
            continue
        d = date.fromisoformat(r["date"])
        if r["type"] == "income":
            bm = f"{d.year + 1}-01" if d.month == 12 else f"{d.year}-{d.month + 1:02d}"
        else:
            bm = f"{d.year}-{d.month:02d}"
        r["budget_month"] = bm
        updated.append((r["date"], r["type"], r["amount"], r["category"], bm))
        print(f"  {r['date']} [{r['type']}] ¥{r['amount']} → budget_month={bm}")

    print()
    print(f"需更新：{len(updated)} 条 | 已有字段：{len(unchanged)} 条")
    if args.yes:
        try:
            save_data(data)
            print("✓ 迁移完成，已写入并备份")
        except RuntimeError as e:
            print(f"⛔ 写入失败：{e}")
            print("💡 下一步：检查 ledger_data.json.bak 备份文件，或导出后联系修复")
            sys.exit(1)
    else:
        print("（使用 --yes 确认写入）")


# ──────────────────── log 命令（一句话记账） ────────────────────

KEYWORD_CATEGORY_MAP = {
    # 日用杂费
    "卫生巾": "日用杂费", "护垫": "日用杂费", "纸巾": "日用杂费",
    "洗发水": "日用杂费", "沐浴露": "日用杂费", "牙膏": "日用杂费",
    "洗衣液": "日用杂费", "洗面奶": "日用杂费",
    # 交通
    "交通费": "交通", "地铁": "交通", "公交": "交通",
    "打车": "交通", "打车费": "交通", "汽油": "交通", "停车费": "交通",
    # 餐饮
    "吃饭": "餐饮", "午饭": "餐饮", "晚饭": "餐饮", "早餐": "餐饮",
    "外卖": "餐饮", "奶茶": "餐饮", "咖啡": "餐饮", "零食": "餐饮",
    "水果": "餐饮", "买菜": "餐饮", "自炊": "餐饮", "餐饮": "餐饮",
    # 固定开支
    "房租": "房租", "水电": "水电杂费",
    # 应急
    "应急": "应急备用金",
    # 犒劳
    "游戏": "犒劳", "皮肤": "犒劳", "烟": "犒劳",
    # 社交
    "社交": "社交基金", "礼物": "社交基金",
    # 家人
    "家人": "家人",
    # 自我投资
    "课程": "自我投资", "书": "自我投资",
}
DEFAULT_CATEGORY = "其他"


def _kw_match(text):
    """从 text 头部匹配已知关键词，返回 (keyword, category) 或 None"""
    for k in sorted(KEYWORD_CATEGORY_MAP.keys(), key=len, reverse=True):
        if text.startswith(k):
            return k, KEYWORD_CATEGORY_MAP[k]
    return None


def parse_log_line(raw):
    """把一句话拆成 [(金额, 类别, 备注)] 列表"""
    # 把 "X元" 统一替换为 "X"
    tmp = re.sub(r"(\d+\.?\d*)元", r"\1", raw.strip())
    results = []
    i = 0
    while i < len(tmp):
        if tmp[i].isspace():
            i += 1
            continue
        consumed = 0  # 本次消耗的字符数

        # 模式A: 金额在前，文字在后  →  "43.56卫生巾" / "43.56 卫生巾"
        ma = re.match(r"^(\d+\.?\d*)\s*([\u4e00-\u9fa5a-zA-Z]+)", tmp[i:])
        # 模式B: 文字在前，金额在后  →  "卫生巾43.56" / "卫生巾 43.56"
        mb = re.match(r"^([\u4e00-\u9fa5a-zA-Z]+)\s*(\d+\.?\d*)", tmp[i:])

        if ma and mb:
            # 两者都匹配？取更长的那个（消耗更多字符）
            if len(ma.group(0)) >= len(mb.group(0)):
                amount, text = float(ma.group(1)), ma.group(2)
            else:
                amount, text = float(mb.group(2)), mb.group(1)
            consumed = max(len(ma.group(0)), len(mb.group(0)))
        elif ma:
            amount, text = float(ma.group(1)), ma.group(2)
            consumed = len(ma.group(0))
        elif mb:
            amount, text = float(mb.group(2)), mb.group(1)
            consumed = len(mb.group(0))
        else:
            # 单个金额，没有文字伴随
            mn = re.match(r"^(\d+\.?\d*)", tmp[i:])
            if mn:
                results.append((float(mn.group(1)), "餐饮", ""))
                i += len(mn.group(0))
            else:
                i += 1  # 跳过无法解析的字符
            continue

        # 从 text 中匹配关键词
        matched = _kw_match(text)
        if matched:
            kw, cat = matched
            results.append((amount, cat, kw))
        else:
            results.append((amount, DEFAULT_CATEGORY, text))
        i += consumed

    return results


def cmd_log(args):
    """一句话记账：自动识别金额和类别"""
    line = args.line.strip()
    if not line:
        print("用法：ledger.py log \"43.56 卫生巾 交通费1元\"")
        sys.exit(1)

    items = parse_log_line(line)
    if not items:
        print(f"未能解析「{line}」，请确认格式，如：43.56 卫生巾 交通费1元")
        sys.exit(1)

    print()
    print("解析结果：")
    for amount, cat, note in items:
        print(f"  ¥{amount:.2f} [{cat}] {note}")
    print()

    if not args.yes:
        confirm = input("确认写入？（输入 yes 确认）：")
        if confirm.strip().lower() != "yes":
            print("已取消")
            return

    for amount, cat, note in items:
        try:
            rec = add_record("expense", amount, cat, note, args.date)
            print(f"✓ ¥{rec['amount']:.2f} [{rec['category']}] {rec['note']}")
        except ValueError as e:
            print(f"⛔ 写入失败：{e}")
            print("💡 下一步：检查金额和类别是否正确，已写入的记录无需重新输入")
            sys.exit(1)

    print()
    cmd_today(args)


# ──────────────────── 工具函数 ────────────────────

def filter_records(records, year=None, month=None, budget_month=None):
    """按实际日期或预算月份筛选记录"""
    result = []
    for r in records:
        d = date.fromisoformat(r["date"])
        bm = r.get("budget_month", f"{d.year}-{d.month:02d}")
        if year is not None and d.year != year:
            continue
        if month is not None and d.month != month:
            continue
        if budget_month is not None and bm != budget_month:
            continue
        result.append(r)
    return result


def summarize_month(records, year, month):
    """返回指定月份的现金流和预算池双轨汇总"""
    cash_records = filter_records(records, year=year, month=month)   # 现金流（按实际日期）
    budget_records = filter_records(records, budget_month=f"{year}-{month:02d}")  # 预算池（按归属月）

    def sum_by_type(recs):
        # 排除期初余额（存量资产，不是收入）— 用字段判断，不依赖文本
        real = [r for r in recs if not r.get("is_balance")]
        inc = sum(r["amount"] for r in real if r["type"] == "income")
        exp = sum(r["amount"] for r in real if r["type"] == "expense")
        return inc, exp

    cash_inc, cash_exp = sum_by_type(cash_records)
    bgt_inc, bgt_exp = sum_by_type(budget_records)

    # 上月底预算池结余（截止到当月之前所有收入 - 所有支出）
    all_before = filter_records(records, budget_month=None)  # 先全部拿，按 budget_month 过滤
    # 重新实现：所有 budget_month < 当月的记录
    target_bm = f"{year}-{month:02d}"
    before_records = []
    for r in records:
        bm = r.get("budget_month")
        if bm and bm < target_bm:
            before_records.append(r)
    prev_bgt_inc = sum(r["amount"] for r in before_records if r["type"] == "income")
    prev_bgt_exp = sum(r["amount"] for r in before_records if r["type"] == "expense")
    prev_balance = prev_bgt_inc - prev_bgt_exp

    return {
        "cash_income": cash_inc,
        "cash_expense": cash_exp,
        "cash_balance": cash_inc - cash_exp,
        "budget_income": bgt_inc,
        "budget_expense": bgt_exp,
        "prev_budget_balance": prev_balance,
        "budget_balance": prev_balance + bgt_inc - bgt_exp,
        "cash_records": cash_records,
        "budget_records": budget_records,
    }


def print_month_summary(records, year, month):
    """打印月度双轨汇总"""
    s = summarize_month(records, year, month)
    _, days_in_month = monthrange(year, month)
    bm_label = f"{year}年{month}月"

    print()
    print("=" * 50)
    print(f"  📅 {bm_label} 财务汇总（双轨版）")
    print("=" * 50)

    # ── 现金流 ──
    print()
    print("  💰 现金流（实际进出账）")
    print("  " + "-" * 40)
    print(f"    收入        ¥{s['cash_income']:>10.2f}")
    print(f"    支出        ¥{s['cash_expense']:>10.2f}")
    print(f"    结余        ¥{s['cash_balance']:>+10.2f}")

    # ── 预算池 ──
    print()
    print("  📊 预算池（归属月份）")
    print("  " + "-" * 40)
    print(f"    上月结转    ¥{s['prev_budget_balance']:>10.2f}")
    print(f"    + 当月收入  ¥{s['budget_income']:>10.2f}")
    print(f"    - 当月支出  ¥{s['budget_expense']:>10.2f}")
    print("  " + "-" * 40)
    status = "✅ 有余额" if s['budget_balance'] >= 0 else "⚠️ 超支！"
    print(f"    预算结余    ¥{s['budget_balance']:>+10.2f}  {status}")

    # 预算超支警示
    if s['budget_expense'] > s['prev_budget_balance'] + s['budget_income']:
        overspend = s['budget_expense'] - (s['prev_budget_balance'] + s['budget_income'])
        print()
        print(f"  ⚠️ 预算超支 ¥{overspend:.2f}！支出用到了下月收入或动用存款。")

    # 储蓄率（现金流）
    if s['cash_income'] > 0:
        save_rate = (s['cash_income'] - s['cash_expense']) / s['cash_income'] * 100
        print()
        print(f"  🏦 储蓄率（现金流）  {save_rate:+.1f}%")
        print(f"    公式：(¥{s['cash_income']:.2f} - ¥{s['cash_expense']:.2f}) / ¥{s['cash_income']:.2f}")

    print()
    print("=" * 50)
    print()


# ──────────────────── 命令实现 ────────────────────

def cmd_income(args):
    if args.source not in INCOME_SOURCES:
        print(f"错误：未知收入来源「{args.source}」")
        print(f"可选：{', '.join(INCOME_SOURCES)}")
        print("💡 下一步：使用 --source 选择一个有效来源，如 --source 平台")
        sys.exit(1)

    # 推断 budget_month（预校验需要）
    if args.date:
        rec_date = args.date
    else:
        rec_date = date.today().isoformat()
    try:
        d = date.fromisoformat(rec_date)
    except ValueError:
        print(f"错误：日期格式无效「{rec_date}」")
        print("💡 下一步：使用 YYYY-MM-DD 格式，如 --date 2026-04-09")
        sys.exit(1)
    if args.budget_month:
        bm = args.budget_month
    else:
        bm = f"{d.year + 1}-01" if d.month == 12 else f"{d.year}-{d.month + 1:02d}"

    # 硬约束：平台/线上收入 → 先校验预估一致性，再写入
    if args.source in ("平台", "75h线上"):
        data = load_data()
        try:
            check_estimate_consistency(data, bm)
        except RuntimeError as e:
            print(f"\n⛔ {e}")
            print("💡 下一步：运行 `ledger validate --month {bm}` 查看详情，或确认预估记录已录入")
            sys.exit(1)

    try:
        rec = add_record("income", args.amount, args.source,
                         args.note or "", args.date, args.budget_month,
                         is_once=args.once, is_balance=args.balance)
    except ValueError as e:
        print(f"错误：{e}")
        print("💡 下一步：检查金额、日期、类别是否正确，或运行 `ledger summary` 查看当前状态")
        sys.exit(1)

    rtype_label = "收入"
    bm_label = f"（归属预算月：{rec['budget_month']}）"
    flags = ""
    if rec.get("is_once"):
        flags += " 🔒一次性"
    if rec.get("is_balance"):
        flags += " 🏦期初余额"
    print(f"✓ 已记录 {rtype_label} ¥{rec['amount']:.2f}  来源：{rec['category']}  "
          f"备注：{rec['note']}  日期：{rec['date']}{flags} {bm_label}")


def cmd_expense(args):
    if args.category not in EXPENSE_CATEGORIES:
        print(f"错误：未知支出类别「{args.category}」")
        print(f"可选：{', '.join(EXPENSE_CATEGORIES)}")
        print("💡 下一步：使用 --category 选择一个有效类别")
        sys.exit(1)
    try:
        rec = add_record("expense", args.amount, args.category,
                         args.note or "", args.date, args.budget_month,
                         is_once=args.once)
    except ValueError as e:
        print(f"错误：{e}")
        print("💡 下一步：检查金额、日期是否正确，或运行 `ledger summary` 查看当前状态")
        sys.exit(1)

    rtype_label = "支出"
    bm_label = f"（归属预算月：{rec['budget_month']}）"
    flags = ""
    if rec.get("is_once"):
        flags += " 🔒一次性"
    print(f"✓ 已记录 {rtype_label} ¥{rec['amount']:.2f}  类别：{rec['category']}  "
          f"备注：{rec['note']}  日期：{rec['date']}{flags} {bm_label}")


def cmd_summary(args):
    data = load_data()
    if args.month:
        try:
            target = datetime.strptime(args.month, "%Y-%m")
        except ValueError:
            print("错误：月份格式应为 YYYY-MM，如 2026-03")
            print("💡 下一步：使用 --month 2026-04 格式重新运行")
            sys.exit(1)
        year, month = target.year, target.month
    else:
        today = date.today()
        year, month = today.year, today.month

    print_month_summary(data["records"], year, month)


def cmd_export(args):
    data = load_data()
    records = data["records"]
    if not records:
        print("暂无记录可导出。")
        return

    csv_path = os.path.join(SCRIPT_DIR, "ledger_export.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["日期", "类型", "金额", "类别/来源", "备注", "预算归属月"])
        for r in records:
            type_label = "收入" if r["type"] == "income" else "支出"
            writer.writerow([
                r["date"], type_label, r["amount"],
                r["category"], r["note"], r.get("budget_month", "-")
            ])
    print(f"✓ 已导出 {len(records)} 条记录到：{csv_path}")


# ──────────────────── 线上阶梯计价 ────────────────────

TIER_TABLE = [
    (0,      12,   50),
    (12,     16,   55),
    (16,     20,   60),
    (20,     28,   65),
    (28,     36,   70),
    (36,     48,   75),
    (48,     9999, 90),
]

def get_tier_and_income(total_minutes):
    total_hours = total_minutes / 60
    for min_h, max_h, price in TIER_TABLE:
        if total_hours < max_h:
            return price, total_minutes / 60 * price, total_hours
    return 90, total_minutes / 60 * 90, total_hours


def cmd_calc_ladder(args):
    data = load_data()
    target_year = int(args.year.split("-")[0]) if args.year else date.today().year
    target_month = int(args.year.split("-")[1]) if args.year else date.today().month

    total_minutes = 0
    detail = []
    for r in data["records"]:
        if r.get("type") != "income" or r.get("category") not in ("平台", "75h线上"):
            continue
        d = date.fromisoformat(r["date"])
        if d.year != target_year or d.month != target_month:
            continue
        note = r.get("note", "")
        # 匹配: X分钟 | X课时 | Xh(但排除 X/h 单价格式)
        m = re.search(r"(\d+\.?\d*)\s*分钟|(\d+\.?\d*)\s*课时|(?<!/)(\d+\.?\d*)\s*h\b", note.lower())
        if m:
            if m.group(1):  # 分钟
                mins = int(float(m.group(1)))
            elif m.group(2):  # 课时 → 转分钟
                mins = int(float(m.group(2)) * 60)
            else:  # h
                mins = int(float(m.group(3)) * 60)
            total_minutes += mins
            detail.append(f"  {r['date']} {note} → {mins}分钟")

    price, income, hours = get_tier_and_income(total_minutes)
    tier_label = f"¥{price}/h"
    for min_h, max_h, p in TIER_TABLE:
        if hours < max_h:
            tier_label = f"¥{p}/h（{min_h}-{max_h}h档）"
            break

    print(f"📊 {target_year}年{target_month}月 线上阶梯统计")
    print("─" * 40)
    for d in detail:
        print(d)
    print("─" * 40)
    print(f"月总课时：{hours:.1f}h（{total_minutes}分钟）")
    print(f"当前档位：{tier_label}")
    print(f"应记收入：¥{income:.2f}")
    if args.show_tiers:
        print("─" * 40)
        print("📐 计价阶梯表：")
        for min_h, max_h, p in TIER_TABLE:
            label = "起薪" if min_h == 0 else f"{min_h}h+"
            print(f"  {label}（<{max_h}h）：¥{p}/h")


# ──────────────────── "还能花多少"计算 ────────────────────

def cmd_remaining(args):
    """按SKILL.md四步公式计算今日还能花多少"""
    data = load_data()
    records = data["records"]

    if args.month:
        try:
            target = datetime.strptime(args.month, "%Y-%m")
        except ValueError:
            print("错误：月份格式应为 YYYY-MM，如 2026-04")
            print("💡 下一步：使用 --month 2026-04 格式重新运行")
            sys.exit(1)
        year, month = target.year, target.month
    else:
        today_d = date.today()
        year, month = today_d.year, today_d.month

    target_bm = f"{year}-{month:02d}"
    _, days_in_month = monthrange(year, month)
    today_d = date.today()

    # ── 第一步：算月收入 ──
    # 收入归属 target 的当月（与支出同月）
    income_bm = target_bm

    actual_income = 0
    est_income = 0
    for r in records:
        if r["type"] != "income":
            continue
        if r.get("is_balance"):
            continue  # 期初余额不算收入
        if r.get("budget_month") != income_bm:
            continue
        amt = r["amount"]
        if "\u23f3" in r.get("note", ""):
            est_income += amt
        else:
            actual_income += amt

    total_income = actual_income + est_income

    # ── 第二步：扣掉不参与日均的支出 ──
    one_time_exp = 0
    daily_exp_total = 0  # 全月实际日常支出（不含一次性和⏳预估）
    est_daily_exp = 0    # ⏳预估日常支出
    today_spent = 0      # 今天已花的日常支出

    for r in records:
        if r["type"] != "expense":
            continue
        if r.get("budget_month") != target_bm:
            continue
        amt = r["amount"]
        note = r.get("note", "")

        if r.get("is_once"):
            one_time_exp += amt
        elif "\u23f3" in note:
            est_daily_exp += amt
        else:
            daily_exp_total += amt
            d = date.fromisoformat(r["date"])
            if d == today_d:
                today_spent += amt

    available_budget = total_income - one_time_exp - est_daily_exp

    # ── 第三步：算日均 ──
    daily_limit = available_budget / days_in_month

    # ── 第四步：算剩余 ──
    rate = (args.rate if args.rate is not None else 20) / 100.0
    spendable_income = total_income * (1 - rate)
    spendable_daily = spendable_income / days_in_month
    today_remaining = spendable_daily - today_spent

    # 本月剩余（考虑储蓄率：可花总额 - 已花日常）
    spendable_budget = total_income * (1 - rate) - one_time_exp - est_daily_exp
    total_usable = spendable_budget - daily_exp_total
    if today_d.month == month and today_d.year == year:
        days_left = days_in_month - today_d.day + 1  # 含今天
    else:
        days_left = days_in_month
    days_left = max(1, days_left)
    daily_left = total_usable / days_left

    # ── 输出 ──
    print()
    print("=" * 50)
    print(f"  \U0001f4b0 {year}年{month}月\u300c还能花多少\u300d")
    print("=" * 50)
    print()
    print(f"  \U0001f4e5 月收入（归属{income_bm}）")
    print(f"    实际收入      \u00a5{actual_income:>10.2f}")
    print(f"    预估收入      \u00a5{est_income:>10.2f}")
    print(f"    合计          \u00a5{total_income:>10.2f}")
    print()
    print(f"  \U0001f4e4 支出分解（归属{target_bm}）")
    print(f"    \U0001f512一次性支出  \u00a5{one_time_exp:>10.2f}（不参与日均）")
    print(f"    \u23f3预估日常    \u00a5{est_daily_exp:>10.2f}")
    print(f"    已花日常      \u00a5{daily_exp_total:>10.2f}")
    print(f"    其中今日已花  \u00a5{today_spent:>10.2f}")
    print()
    print(f"  \U0001f9ee 日均计算")
    print(f"    可用日常预算  \u00a5{available_budget:>10.2f}（收入-一次性-预估）")
    print(f"    日均上限      \u00a5{daily_limit:>10.2f}（\u00f7{days_in_month}天）")
    print(f"    储蓄率        {rate*100:.0f}% \u2192 可花{(1-rate)*100:.0f}%")
    print(f"    日均可花      \u00a5{spendable_daily:>10.2f}")
    print()
    print(f"  \u2705 今日剩余    \u00a5{today_remaining:>10.2f}（日均可花-今日已花）")
    print(f"  \U0001f4c5 剩余总额    \u00a5{total_usable:>10.2f}（{days_left}天\u2192\u65e5\u5747\u00a5{daily_left:.0f}）")

    # ── 今日餐饮状态 ──
    bp = load_budget_plan()
    day_key = today_d.strftime("%m-%d")
    full_date = today_d.isoformat()

    meal_plan_amt = 0
    meal_plan_label = ""
    if bp and "daily_plan_april" in bp:
        plan = bp["daily_plan_april"].get(day_key)
        if plan:
            meal_plan_amt = plan.get("food_budget", 0)
            t = plan.get("type", "")
            label_map = {"green": "\U0001f7e2自炊", "yellow": "\U0001f7e1外卖", "red": "\U0001f534馆子"}
            meal_plan_label = label_map.get(t, plan.get("label", ""))

    today_meal_recs = [r for r in records
                      if r.get("date") == full_date
                      and r.get("type") == "expense"
                      and r.get("category") == "餐饮"]
    today_meal_actual = sum(r["amount"] for r in today_meal_recs)
    meal_remaining = meal_plan_amt - today_meal_actual if meal_plan_amt else 0

    print()
    print(f"  \U0001f35d 今日餐饮")
    if meal_plan_label:
        print(f"    计划：{meal_plan_label} \u00a5{meal_plan_amt}")
    else:
        print(f"    计划：暂无计划")
    if today_meal_actual > 0:
        diff = today_meal_actual - meal_plan_amt
        if abs(diff) <= 0.01:
            status_label = "恰好"
        elif diff > 0:
            status_label = f"超\u00a5{diff:.2f}"
        else:
            status_label = f"省\u00a5{-diff:.2f}"
        print(f"    实际：\u00a5{today_meal_actual:.2f}（{len(today_meal_recs)}笔）")
        print(f"    剩余：\u00a5{meal_remaining:.2f}（{status_label}）")
    else:
        print(f"    实际：待记录")
        if meal_plan_amt:
            print(f"    剩余：\u00a5{meal_remaining:.2f}")
    print()
    print("=" * 50)


# ──────────────────── 预估一致性校验 ────────────────────

def check_estimate_consistency(data, budget_month):
    """硬约束：新增平台/线上实收前，必须先扣减对应预估。

    逻辑：
    1. 记录当前⏳预估的hash（内容指纹）
    2. 如果预估没变过，但有新增实收 → 阻断
    3. 只要预估内容变了（金额或备注），视为已手动更新，放行
    """
    estimates = [r for r in data.get("records", [])
                 if isinstance(r, dict)
                 and r.get("type") == "income"
                 and r.get("budget_month") == budget_month
                 and "⏳" in r.get("note", "")
                 and r.get("category") in ("平台", "75h线上")]
    if not estimates:
        return  # 没有预估，无需检查

    # 计算当前预估指纹（金额+备注的拼接hash）
    est_fingerprint = "|".join(
        f"{r['amount']}:{r['note']}" for r in sorted(estimates, key=lambda x: x["date"])
    )

    state_file = os.path.join(SCRIPT_DIR, ".estimate_state.json")
    prev_fp = None
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
            prev_fp = state.get(budget_month, {}).get("est_fingerprint")
        except Exception:
            pass

    if prev_fp is not None and prev_fp == est_fingerprint:
        print()
        print("=" * 60)
        print(f"  ⛔ 预估一致性校验失败！")
        print(f"  预算月 {budget_month} 的⏳预估记录尚未更新。")
        print()
        print(f"  → 新增平台/线上实收前，必须先扣减对应预估。")
        print(f"    例如：预估 480min → 440min（扣掉本次上课分钟数）")
        print("=" * 60)
        print()
        raise RuntimeError("预估未同步扣减，记账已阻断。请先更新⏳预估记录。")

    # 校验通过，保存当前指纹
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except Exception:
            pass
    if budget_month not in state:
        state[budget_month] = {}
    state[budget_month]["est_fingerprint"] = est_fingerprint
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def cmd_validate(args):
    """手动校验预估一致性"""
    data = load_data()
    if args.month:
        try:
            datetime.strptime(args.month, "%Y-%m")
        except ValueError:
            print("错误：月份格式应为 YYYY-MM，如 2026-04")
            print("💡 下一步：使用 --month 2026-04 格式重新运行")
            sys.exit(1)
        bm = args.month
    else:
        today = date.today()
        bm = f"{today.year}-{today.month:02d}"

    # 重置指纹，强制下次新增时重新校验
    state_file = os.path.join(SCRIPT_DIR, ".estimate_state.json")
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except Exception:
            pass

    estimates = [r for r in data.get("records", [])
                 if isinstance(r, dict)
                 and r.get("type") == "income"
                 and r.get("budget_month") == bm
                 and "⏳" in r.get("note", "")
                 and r.get("category") in ("平台", "75h线上")]

    if not estimates:
        print(f"ℹ️ 预算月 {bm} 无⏳预估记录，无需校验")
        return

    est_fingerprint = "|".join(
        f"{r['amount']}:{r['note']}" for r in sorted(estimates, key=lambda x: x["date"])
    )

    if bm not in state:
        state[bm] = {}
    # 清除指纹 → 下次 check_estimate_consistency 视为首次，自动放行
    state[bm].pop("est_fingerprint", None)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"✓ 预算月 {bm} 预估校验通过，指纹已清除，下次记实收将放行")
    for r in estimates:
        print(f"  ⏳ ¥{r['amount']}  {r['note']}")


def cmd_plan_modify(args):
    """修改每日餐饮计划"""
    if not BUDGET_PLAN_FILE or not os.path.exists(BUDGET_PLAN_FILE):
        print("⛔ 未找到 budget_plan.json")
        sys.exit(1)

    with open(BUDGET_PLAN_FILE, "r", encoding="utf-8") as f:
        bp = json.load(f)

    plan = bp.get("daily_plan_april", {})
    dates = [d.strip() for d in args.dates.split(",")]
    
    # 默认预算
    defaults = {"green": 30, "yellow": 43, "red": 39}
    labels = {"green": "自炊", "yellow": "外卖", "red": "馆子"}
    
    budget = args.budget if args.budget else defaults.get(args.type, 30)
    
    changes = []
    for d in dates:
        if d in plan:
            old_type = plan[d].get("type")
            changes.append({
                "date": d,
                "old": f"{labels.get(old_type, '?')} ¥{plan[d].get('food_budget', '?')}",
                "new": f"{labels.get(args.type, '?')} ¥{budget}"
            })
            plan[d]["type"] = args.type
            plan[d]["label"] = labels.get(args.type, args.type)
            plan[d]["food_budget"] = budget
            plan[d]["meals"] = f"{labels.get(args.type)}(调整后)"
    
    if not args.yes:
        print("=== 预览修改 ===")
        for c in changes:
            print(f"  {c['date']}: {c['old']} → {c['new']}")
        ans = input("确认修改? (y/n): ").strip().lower()
        if ans != 'y':
            print("已取消")
            return

    # 重新计算吃饭总预算
    total_food = sum(p["food_budget"] for p in plan.values())
    bp["shared_budget"]["categories"]["吃饭"]["amount"] = total_food
    bp["shared_budget"]["categories"]["吃饭"]["sub"]["自炊22"] = sum(
        1 for p in plan.values() if p.get("type") == "green") * 30
    bp["shared_budget"]["categories"]["吃饭"]["sub"]["外卖42"] = sum(
        1 for p in plan.values() if p.get("type") == "yellow") * 43
    bp["shared_budget"]["categories"]["吃饭"]["sub"]["下馆子36"] = sum(
        1 for p in plan.values() if p.get("type") == "red") * 39
    bp["shared_budget"]["categories"]["吃饭"]["sub"]["冗余缓冲"] = 15

    with open(BUDGET_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(bp, f, ensure_ascii=False, indent=2)
    print(f"✓ 已修改 {len(changes)} 天的餐饮计划")


def cmd_last(args):
    """最近一条记录"""
    data = load_data()
    records = data.get("records", [])
    if not records:
        print("暂无记录")
        return
    rec = records[-1]
    cat = rec.get("category", rec.get("类别/来源", ""))
    note = rec.get("note", rec.get("备注", ""))
    print(f"{rec['date']}  {rec['type']}  ¥{rec['amount']}  [{cat}]  {note}")


def cmd_today(args):
    """今日餐饮计划 vs 实际"""
    bp = load_budget_plan()
    data = load_data()
    today = date.today()
    day_key = today.strftime("%m-%d")  # "04-02"
    full_date = today.isoformat()       # "2026-04-02"

    # 获取今日计划
    plan = None
    plan_amt = 0
    plan_label = ""
    if bp and "daily_plan_april" in bp:
        plan = bp["daily_plan_april"].get(day_key)
        if plan:
            plan_amt = plan.get("food_budget", 0)
            t = plan.get("type", "")
            label_map = {"green": "🟢自炊", "yellow": "🟡外卖", "red": "🔴馆子"}
            plan_label = label_map.get(t, plan.get("label", ""))

    # 获取今日实际（餐饮）
    today_recs = [r for r in data["records"]
                  if r.get("date") == full_date
                  and r.get("type") == "expense"
                  and r.get("category") == "餐饮"]
    actual_amt = sum(r["amount"] for r in today_recs)
    diff = actual_amt - plan_amt if plan_amt else 0
    status = ("ok" if abs(diff) <= 0.01 else
              f"超¥{diff:.2f}" if diff > 0 else
              f"省¥{-diff:.2f}" if plan_amt else "待记录")

    print()
    print(f"=== 今日 {full_date} ===")
    if plan_label:
        print(f"计划：{plan_label} ¥{plan_amt}")
    else:
        print(f"计划：暂无计划（不在4月）")
    if actual_amt > 0:
        print(f"实际：¥{actual_amt:.2f}（{len(today_recs)}笔）")
        print(f"差额：{status}")
    else:
        print(f"实际：待记录")
    print()


# ──────────────────── 周状态命令 ────────────────────

WEEK_RANGES = {
    1: ("04-01", "04-07"),
    2: ("04-08", "04-14"),
    3: ("04-15", "04-21"),
    4: ("04-22", "04-30"),
}

def _print_food_day(d, full_d, bp, food_recs, total):
    """打印单日餐饮对比，返回 (actual, plan, total_actual, total_plan)"""
    plan_amt = 0
    plan_label = ""
    month_key = full_d[:7]
    if bp and f"daily_plan_{month_key}" in bp:
        p = bp[f"daily_plan_{month_key}"].get(d, {})
    elif bp and "daily_plan_april" in bp:
        p = bp["daily_plan_april"].get(d, {})
    else:
        p = {}
    plan_amt = p.get("food_budget", 0)
    t = p.get("type", "")
    lm = {"green": "🟢自炊", "yellow": "🟡外卖", "red": "🔴馆子"}
    plan_label = lm.get(t, p.get("label", ""))

    recs = [r for r in food_recs if r["date"] == full_d]
    actual = sum(r["amount"] for r in recs)
    if actual > 0:
        diff = actual - plan_amt
        diff_label = (f"超¥{diff:.2f}" if diff > 0 else f"省¥{-diff:.2f}")
        print(f"  {d} | {plan_label} | 实际¥{actual:.2f}/计划¥{plan_amt} | {diff_label}")
        total[0] += actual
        total[1] += plan_amt
    elif plan_amt > 0:
        print(f"  {d} | {plan_label} | 实际待记录/计划¥{plan_amt}")


def cmd_week_status(args):
    """显示指定周/月的餐饮计划vs实际"""
    # 默认当月
    target_month = args.month or date.today().strftime("%Y-%m")
    year, mon = target_month.split("-")
    _, last_day = monthrange(int(year), int(mon))

    bp = load_budget_plan()
    data = load_data()

    # 如果指定了 --week，计算该周范围；否则全月
    if args.week:
        if args.week not in WEEK_RANGES:
            print("错误：--week 必须为 1~4")
            sys.exit(1)
        ws, we = WEEK_RANGES[args.week]
        start_full = f"{year}-{ws}"
        end_full = f"{year}-{we}"
        s_day = int(ws.split("-")[1])
        e_day = int(we.split("-")[1])
    else:
        start_full = f"{year}-{mon}-01"
        end_full = f"{year}-{mon}-{last_day:02d}"
        s_day = 1
        e_day = last_day

    food_recs = [r for r in data["records"]
                 if start_full <= r["date"] <= end_full
                 and r.get("type") == "expense"
                 and r.get("category") == "餐饮"]

    total = [0, 0]  # [actual, plan]
    print()
    title = f"第{args.week}周" if args.week else "全月"
    ds = start_full[5:]
    de = end_full[5:]
    print(f"=== {title} 餐饮计划 vs 实际（{ds} ~ {de}）===")

    for day_num in range(s_day, e_day + 1):
        d = f"{year}-{mon}-{day_num:02d}"
        _print_food_day(d[5:], d, bp, food_recs, total)

    if total[0] > 0:
        remaining = total[1] - total[0]
        print(f"\n  累计：实际¥{total[0]:.2f} / 计划¥{total[1]:.0f} | 余¥{remaining:.2f}")
    print()


# ──────────────────── 账户状态命令 ────────────────────

def cmd_accounts(args):
    """显示共同账户月预算状态"""
    bp = load_budget_plan()
    if not bp:
        print("ℹ️ 未找到 budget_plan.json，跳过预算对比")
        bp = {}

    data = load_data()
    today = date.today()
    bm = today.strftime("%Y-%m")

    # 从 bp 中读取共同账户预算
    cats = bp.get("shared_budget", {}).get("categories", {})
    # 映射：ledger category -> budget plan key
    cat_map = {
        "餐饮": "吃饭",
        "交通": "交通",
        "日用杂费": "日用杂费",
        "应急备用金": "应急备用金",
        "房租": "房租",
        "水电杂费": "水电杂费",
    }

    # 统计本月各共同账户已发生额
    month_recs = [r for r in data["records"]
                  if r.get("date", "").startswith(bm)
                  and r.get("type") == "expense"
                  and r.get("category") in cat_map]

    spent = {}
    for r in month_recs:
        c = r["category"]
        spent[c] = spent.get(c, 0) + r["amount"]

    print()
    print(f"=== {bm} 共同账户 ===")
    total_budget = 0
    total_spent = 0
    for ledger_cat, bp_key in cat_map.items():
        bgt_info = cats.get(bp_key, {})
        bgt_amt = bgt_info.get("amount", 0) if isinstance(bgt_info, dict) else bgt_info
        s = spent.get(ledger_cat, 0)
        remain = bgt_amt - s
        total_budget += bgt_amt
        total_spent += s
        status = "OK" if remain >= 0 else "OVER"
        print(f"  {bp_key:6s} | 预算¥{bgt_amt:6.0f} | 已花¥{s:6.2f} | 剩余¥{remain:6.2f} | {status}")
    plan_total = bp.get("shared_budget", {}).get("total", total_budget)
    print(f"  {'合计':6s} | 预算¥{plan_total:6.0f} | 已花¥{total_spent:6.2f} | 剩余¥{plan_total-total_spent:6.2f}")
    print()


# ──────────────────── 预算执行检查命令 ────────────────────

def cmd_budget_check(args):
    """显示本月预算执行情况（预算 vs 实际，超支预警）"""
    bp = load_budget_plan()
    if not bp:
        print("❌ 未找到 budget_plan.json")
        print("💡 下一步：确认 workspace/finance/budget_plan.json 是否存在，或先运行预算计划配置")
        sys.exit(1)

    data = load_data()
    
    # 确定查询月份
    if args.month:
        try:
            datetime.strptime(args.month, "%Y-%m")
        except ValueError:
            print("错误：月份格式应为 YYYY-MM，如 2026-04")
            print("💡 下一步：使用 --month 2026-04 格式重新运行")
            sys.exit(1)
        bm = args.month
    else:
        today = date.today()
        bm = today.strftime("%Y-%m")

    # 从 bp 中读取共同账户预算
    cats = bp.get("shared_budget", {}).get("categories", {})
    
    # 映射：ledger category -> budget plan key
    cat_map = {
        "餐饮": "吃饭",
        "零食水果": "零食水果",
        "交通": "交通",
        "日用杂费": "日用杂费",
        "应急备用金": "应急备用金",
        "房租": "房租",
        "水电杂费": "水电杂费",
    }

    # 统计本月各共同账户已发生额
    month_recs = [r for r in data["records"]
                  if r.get("date", "").startswith(bm)
                  and r.get("type") == "expense"
                  and r.get("category") in cat_map]

    spent = {}
    for r in month_recs:
        c = r["category"]
        spent[c] = spent.get(c, 0) + r["amount"]

    # 计算超支
    over_total = 0.0
    over_cats = []
    
    print()
    print(f"=== {bm} 预算执行情况 ===")
    print()
    print(f"{'类别':<10} {'预算':>8} {'实际':>8} {'剩余':>8} {'状态':>10}")
    print("-" * 48)
    
    total_budget = 0
    total_spent = 0
    
    for ledger_cat, bp_key in cat_map.items():
        bgt_info = cats.get(bp_key, {})
        bgt_amt = bgt_info.get("amount", 0) if isinstance(bgt_info, dict) else bgt_info
        s = spent.get(ledger_cat, 0)
        remain = bgt_amt - s
        total_budget += bgt_amt
        total_spent += s
        
        if remain < 0:
            status = "⚠️ 超支"
            over_total += abs(remain)
            over_cats.append(f"{ledger_cat}+¥{abs(remain):.2f}")
        elif remain == bgt_amt and s == 0:
            status = "未发生"
        else:
            status = "✅"
        
        print(f"{ledger_cat:<10} ¥{bgt_amt:>7.0f} ¥{s:>7.2f} ¥{remain:>7.2f} {status:>10}")
    
    print("-" * 48)
    plan_total = bp.get("shared_budget", {}).get("total", total_budget)
    total_remain = plan_total - total_spent
    print(f"{'合计':<10} ¥{plan_total:>7.0f} ¥{total_spent:>7.2f} ¥{total_remain:>7.2f}")
    
    if over_total > 0:
        print()
        print(f"❗ 超支总额：¥{over_total:.2f}（{', '.join(over_cats)}）")
    else:
        print()
        print("✅ 所有类别均在预算内")
    
    print()


# ⚠️ 危险泛词列表：匹配多条时强制二次确认
DANGEROUS_KEYWORDS = [
    "吃饭", "午饭", "晚餐", "早饭", "午饭", "晚饭", "饭",
    "零食", "水果", "饮料",
    "交通", "车费", "公交", "地铁",
    "买", "购物", "采购",
]

def cmd_delete(args):
    """删除记录：按备注关键字匹配，需确认
    
    ⚠️ 安全增强：
    - 匹配多条且关键字为泛词时，强制二次确认（即使有 --yes）
    - 显示警告并要求输入完整确认语
    """
    data = load_data()
    keyword = args.keyword
    budget_month = args.month

    matches = []
    for i, r in enumerate(data["records"]):
        if keyword.lower() not in r.get("note", "").lower():
            continue
        if budget_month and r.get("budget_month") != budget_month:
            continue
        matches.append((i, r))

    if not matches:
        print(f"未找到包含「{keyword}」的记录")
        return

    print(f"找到 {len(matches)} 条匹配记录：")
    for idx, (i, r) in enumerate(matches):
        once = " [一次性]" if r.get("is_once") else ""
        bal = " [期初余额]" if r.get("is_balance") else ""
        print(f"  {idx+1}. {r['date']} | {r['type']} ¥{r['amount']} | {r['note']}{once}{bal}")

    # ⚠️ 危险泛词检测：匹配多条时强制二次确认
    is_dangerous = len(matches) > 1 and any(kw in keyword for kw in DANGEROUS_KEYWORDS)
    
    if is_dangerous:
        print()
        print("⚠️  警告：检测到危险泛词，可能误删多条历史记录！")
        print(f"   关键字「{keyword}」匹配了 {len(matches)} 条记录")
        print()
        print("   请再次确认：输入「我确认要删除以上全部记录」继续")
        confirm = input("   > ")
        if confirm.strip() != "我确认要删除以上全部记录":
            print("已取消")
            return
    elif not args.yes:
        confirm = input(f"\n确认删除以上 {len(matches)} 条？输入 yes 确认：")
        if confirm.strip().lower() != "yes":
            print("已取消")
            return

    # 从后往前删，避免索引偏移
    try:
        for i, r in reversed(matches):
            del data["records"][i]

        save_data(data)
        print(f"✓ 已删除 {len(matches)} 条记录")
    except RuntimeError as e:
        print(f"⛔ 写入失败：{e}")
        print("💡 下一步：检查 ledger_data.json.bak 备份文件，或手动运行 `ledger export` 导出数据后联系修复")
        sys.exit(1)
    except Exception as e:
        print(f"⛔ 删除过程中出错：{e}")
        print("💡 下一步：运行 `ledger summary` 检查数据状态，不要重复执行删除")
        sys.exit(1)


# ──────────────────── 批量修改命令 ────────────────────

def cmd_modify(args):
    """批量修改记录字段（预览模式默认，仅 --yes 确认后写入）"""
    data = load_data()
    records = data["records"]

    # ── 筛选记录 ──
    matched = []
    for i, r in enumerate(records):
        # 日期过滤（实际发生日期，非预算归属月）
        if args.date:
            if r["date"] != args.date:
                continue
        if args.from_date:
            if r["date"] < args.from_date:
                continue
        if args.to_date:
            if r["date"] > args.to_date:
                continue
        # 月份过滤
        if args.month:
            bm = r.get("budget_month", "")
            # 兼容 "YYYY-MM" 和 "YYYY-MM-DD" 两种格式
            bm_prefix = bm[:7] if bm else ""
            if bm_prefix != args.month:
                continue
        # 关键字过滤（匹配备注）
        if args.keyword:
            if args.keyword.lower() not in r.get("note", "").lower():
                continue
        # 类型过滤
        if args.type:
            if r["type"] != args.type:
                continue
        # 类别过滤
        if args.category:
            if r.get("category") != args.category:
                continue
        matched.append((i, r))

    if not matched:
        print("未找到匹配记录，请检查筛选条件")
        return

    # ── 预览变更 ──
    changes = []
    for i, r in matched:
        before = {k: r.get(k) for k in ["amount", "category", "note", "date"]}
        after = dict(before)

        if args.set_amount is not None:
            after["amount"] = args.set_amount
        if args.set_category:
            after["category"] = args.set_category
        if args.set_note is not None:
            after["note"] = args.set_note
        if args.set_date:
            after["date"] = args.set_date

        # 检查是否有实质变化
        if before == after:
            continue

        # 重建 shares（共同账户支出）
        new_r = dict(r)
        new_r["amount"] = after["amount"]
        new_r["category"] = after["category"]
        new_r["note"] = after["note"]
        new_r["date"] = after["date"]

        cat = after["category"]
        amt = after["amount"]
        rtype = r["type"]

        # 自动维护分账字段
        if rtype == "expense" and cat in SHARED_CATEGORIES:
            new_r["user_share"] = round(amt * USER_RATIO, 2)
            new_r["girlfriend_share"] = round(amt * GIRLFRIEND_RATIO, 2)
        elif rtype == "expense" and args.set_category and cat not in SHARED_CATEGORIES:
            # 切换到个人类别 → 清除分账
            new_r.pop("user_share", None)
            new_r.pop("girlfriend_share", None)

        # 餐饮同步更新 planned_amount（日期可能也变了）
        if rtype == "expense" and cat == "餐饮":
            new_plan = get_daily_plan(after["date"])
            if new_plan is not None:
                new_r["planned_amount"] = new_plan
            elif "planned_amount" in new_r:
                new_r.pop("planned_amount")

        changes.append({
            "index": i,
            "before": before,
            "after": after,
            "record": new_r,
        })

    if not changes:
        print("筛选的记录没有需要变更的字段")
        return

    # ── 展示预览 ──
    print()
    print(f"【预览】共 {len(changes)} 条记录将变更：")
    print()
    for ch in changes:
        i = ch["index"]
        b = ch["before"]
        a = ch["after"]
        print(f"  [{i+1}] {b['date']} | {b['category']} ¥{b['amount']} | {b['note']}")
        arrows = []
        if a['amount'] != b['amount']:
            arrows.append(f"金额: ¥{b['amount']} → ¥{a['amount']}")
        if a['category'] != b['category']:
            arrows.append(f"类别: {b['category']} → {a['category']}")
        if a['note'] != b['note']:
            arrows.append(f"备注: {b['note']!r} → {a['note']!r}")
        if a['date'] != b['date']:
            arrows.append(f"日期: {b['date']} → {a['date']}")
        for arrow in arrows:
            print(f"       → {arrow}")
        print()

    if not args.yes:
        print(f"提示：以上 {len(changes)} 条记录将写入，输入 --yes 确认生效")
        print(f"用法示例：ledger.py modify --keyword \"{args.keyword or args.date or ''}\" --set-category {args.set_category or '...'} --set-note \"...\" --yes")
        return

    # ── 写入 ──
    try:
        for ch in changes:
            idx = ch["index"]
            records[idx].update(ch["record"])

        save_data(data)
        print(f"✓ 已修改 {len(changes)} 条记录")
    except RuntimeError as e:
        print(f"⛔ 写入失败：{e}")
        print("💡 下一步：检查 ledger_data.json.bak 备份文件，或手动运行 `ledger export` 导出数据后联系修复")
        sys.exit(1)
    except Exception as e:
        print(f"⛔ 修改过程中出错：{e}")
        print("💡 下一步：运行 `ledger summary` 检查数据状态，不要重复执行修改")
        sys.exit(1)


# ──────────────────── CLI 入口 ────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="ledger",
        description="💰 简易记账工具（双轨版）— 现金流 + 预算池 分开计算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_income = subparsers.add_parser("income", help="记录一笔收入")
    p_income.add_argument("amount", type=float, help="收入金额")
    p_income.add_argument("--source", required=True, choices=INCOME_SOURCES, help="收入来源")
    p_income.add_argument("--note", default="", help="备注")
    p_income.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="日期，默认今天")
    p_income.add_argument("--budget-month", default=None, metavar="YYYY-MM",
                          help="归属预算月份，默认：下个月（收入）")
    p_income.add_argument("--once", action="store_true",
                          help="一次性收入（不参与日均计算）")
    p_income.add_argument("--balance", action="store_true",
                          help="期初余额标记（存量资产，不计入收入）")
    p_income.set_defaults(func=cmd_income)

    # ── modify ──
    p_modify = subparsers.add_parser("modify", help="批量修改记录字段（默认预览模式）")
    p_modify.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                          help="限定具体日期")
    p_modify.add_argument("--from-date", dest="from_date", default=None, metavar="YYYY-MM-DD",
                          help="起始日期（包含）")
    p_modify.add_argument("--to", dest="to_date", default=None, metavar="YYYY-MM-DD",
                          help="结束日期（包含）")
    p_modify.add_argument("--month", default=None, metavar="YYYY-MM",
                          help="限定预算归属月")
    p_modify.add_argument("--keyword", "-k", default=None, help="按备注关键字筛选")
    p_modify.add_argument("--type", choices=["income", "expense"], default=None,
                          help="限定记录类型")
    p_modify.add_argument("--category", default=None, choices=EXPENSE_CATEGORIES,
                          help="限定当前类别")
    p_modify.add_argument("--set-amount", type=float, default=None, metavar="N",
                          help="设置新金额")
    p_modify.add_argument("--set-category", default=None, choices=EXPENSE_CATEGORIES,
                          help="设置新类别")
    p_modify.add_argument("--set-note", default=None, metavar="TEXT",
                          help="设置新备注（直接写字符串）")
    p_modify.add_argument("--set-date", default=None, metavar="YYYY-MM-DD",
                          help="设置新日期")
    p_modify.add_argument("--yes", "-y", action="store_true",
                          help="跳过预览，直接写入（配合筛选条件使用）")
    p_modify.set_defaults(func=cmd_modify)

    p_expense = subparsers.add_parser("expense", help="记录一笔支出")
    p_expense.add_argument("amount", type=float, help="支出金额")
    p_expense.add_argument("--category", required=True, choices=EXPENSE_CATEGORIES, help="支出类别")
    p_expense.add_argument("--note", default="", help="备注")
    p_expense.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="日期，默认今天")
    p_expense.add_argument("--budget-month", default=None, metavar="YYYY-MM",
                          help="归属预算月份，默认：当月（支出）")
    p_expense.add_argument("--once", action="store_true",
                          help="一次性支出（不参与日均计算）")
    p_expense.add_argument("--yes", "-y", action="store_true",
                          help="跳过确认直接写入（expense 无需确认，此参数仅为接口一致性保留）")
    p_expense.set_defaults(func=cmd_expense)

    p_log = subparsers.add_parser("log", help="一句话记账，自动识别金额和类别")
    p_log.add_argument("line", help="记账字符串，如：43.56 卫生巾 交通费1元")
    p_log.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="日期，默认今天")
    p_log.add_argument("--yes", "-y", action="store_true", help="跳过确认直接写入")
    p_log.set_defaults(func=cmd_log)

    p_delete = subparsers.add_parser("delete", help="删除记录（按备注关键字匹配）")
    p_delete.add_argument("keyword", help="备注关键字，匹配备注包含此文字的记录")
    p_delete.add_argument("--month", default=None, metavar="YYYY-MM", help="限定预算月份")
    p_delete.add_argument("--yes", "-y", action="store_true", help="跳过确认直接删除")
    p_delete.set_defaults(func=cmd_delete)

    p_today = subparsers.add_parser("today", help="今日餐饮计划 vs 实际")
    p_today.set_defaults(func=cmd_today)

    p_last = subparsers.add_parser("last", help="最近一条记录")
    p_last.set_defaults(func=cmd_last)

    p_week = subparsers.add_parser("week-status", help="显示指定周的餐饮计划vs实际，或--month出全月")
    p_week.add_argument("--week", type=int, choices=[1,2,3,4], help="第几周（1~4）")
    p_week.add_argument("--month", default=None, metavar="YYYY-MM", help="指定月份出全月，默认当月")
    p_week.set_defaults(func=cmd_week_status)

    p_accounts = subparsers.add_parser("accounts", help="显示共同账户月预算状态")
    p_accounts.set_defaults(func=cmd_accounts)

    p_budget_check = subparsers.add_parser("budget-check", help="预算执行检查（预算 vs 实际，超支预警）")
    p_budget_check.add_argument("--month", default=None, metavar="YYYY-MM", help="指定月份，默认当月")
    p_budget_check.set_defaults(func=cmd_budget_check)

    p_summary = subparsers.add_parser("summary", help="查看月度汇总（双轨）")
    p_summary.add_argument("--month", default=None, help="指定月份，格式 YYYY-MM，默认当月")
    p_summary.set_defaults(func=cmd_summary)

    p_export = subparsers.add_parser("export", help="导出 CSV（含预算归属月）")
    p_export.set_defaults(func=cmd_export)

    p_remain = subparsers.add_parser("remaining", help="本月还能花多少（按储蓄率）")
    p_remain.add_argument("--month", default=None, metavar="YYYY-MM", help="指定月份，默认当月")
    p_remain.add_argument("--rate", type=float, default=None, metavar="N",
                          help="储蓄率百分比，默认20（即存20%%花80%%）")
    p_remain.set_defaults(func=cmd_remaining)

    p_calc = subparsers.add_parser("calc-ladder", help="计算当月线上阶梯收入")
    p_calc.add_argument("--year", default=None, metavar="YYYY-MM", help="指定月份，默认当月")
    p_calc.add_argument("--show-tiers", action="store_true", help="显示完整阶梯表")
    p_calc.set_defaults(func=cmd_calc_ladder)

    p_plan = subparsers.add_parser("plan-modify", help="修改每日餐饮计划")
    p_plan.add_argument("--dates", required=True, help="日期列表，逗号分隔，如 04-12,04-13")
    p_plan.add_argument("--type", required=True, choices=["green", "yellow", "red"], help="类型")
    p_plan.add_argument("--budget", type=int, help="覆盖预算金额（默认: 30/43/39）")
    p_plan.add_argument("--yes", "-y", action="store_true", help="跳过预览")
    p_plan.set_defaults(func=cmd_plan_modify)

    p_migrate = subparsers.add_parser("migrate", help="迁移旧数据，补充 budget_month 字段")
    p_migrate.add_argument("--yes", "-y", action="store_true",
                          help="跳过预览，直接写入")
    p_migrate.set_defaults(func=cmd_migrate)

    p_validate = subparsers.add_parser("validate", help="校验预估与实收一致性")
    p_validate.add_argument("--month", default=None, metavar="YYYY-MM", help="预算月，默认当月+1")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        args.func(args)
    except SystemExit:
        raise  # argparse 或 sys.exit 正常退出
    except FileNotFoundError as e:
        print(f"\n⛔ 文件未找到：{e}")
        print("💡 下一步：确认 ledger_data.json 存在，或运行 `ledger income 0 --source 其他 --balance` 初始化")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"\n⛔ 数据文件损坏（JSON 解析失败）：{e}")
        print("💡 下一步：")
        print("  1. 检查 ledger_data.json.bak 是否存在")
        print("  2. 如有备份，运行: copy ledger_data.json.bak ledger_data.json")
        print("  3. 如无备份，导出数据: 手动检查 ledger_export.csv")
        sys.exit(1)
    except Exception as e:
        print(f"\n⛔ 未预期错误：{type(e).__name__}: {e}")
        print("💡 下一步：不要重复执行同一命令，先运行 `ledger summary` 检查数据状态")
        sys.exit(1)


if __name__ == "__main__":
    main()

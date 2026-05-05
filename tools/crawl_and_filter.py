"""
两阶段校园通知爬虫：
Phase 1: 爬取所有站点的文章列表（快）
Phase 2: 基于标题筛选相关性，只爬命中的详情页
"""
import sys, os, json, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler_core import load_config, fetch_page, parse_date, parse_article_content, extract_structured_info, normalize_url
from crawler_logger import setup_logging, get_logger
import site_handlers

setup_logging(enable_file=False)
logger = get_logger()

# ── Phase 1: 仅列表 ──

def scrape_all_lists(config, days=30):
    """爬取所有站点的文章列表（不抓详情页）"""
    cutoff = datetime.now() - timedelta(days=days)
    all_articles = []

    for site in config.get('sites', []):
        code = site['code']
        name = site['name']
        handler = site_handlers.SITE_HANDLERS.get(code)
        if not handler:
            print(f"  [{code}] 跳过：无handler")
            continue

        print(f"  [{code}] {name}...", end=' ')
        try:
            html = fetch_page(site['url'])
            if not html:
                print("页面获取失败")
                continue

            if hasattr(handler, 'parse_article_list'):
                articles = handler.parse_article_list(html, site['url'])
            else:
                # fallback: 直接用通用解析
                from crawler_core import parse_article_list as generic_parse
                articles, _ = generic_parse(html, site['url'])

            # 有日期的按日期过滤，没日期的保留
            dated = [a for a in articles if a.get('parsed_date') and a['parsed_date'] >= cutoff]
            undated = [a for a in articles if not a.get('parsed_date')]
            combined = dated + undated[:5]  # 无日期最多保留5条

            for a in combined:
                a['source_site'] = name
                a['site_url'] = site['url']

            all_articles.extend(combined)
            print(f"{len(combined)} 条")
        except Exception as e:
            print(f"错误: {e}")

    return all_articles


# ── Phase 2: 筛选 + 详情 ──

# 与 filter_useful.py 相同的关键词
HIGH_KEYWORDS = [
    '物理', '物理竞赛', '物理实验', '物理建模', '物理学术',
    '数学建模', '数学竞赛', '数学', '科学竞赛',
    '挑战杯', '大创', '大学生创新创业',
    '师范', '教学技能', '讲课比赛', '微课', '模拟课堂',
    '教师资格', '教育实习',
    '奖学金', '国家奖学金', '励志奖学金', '优秀学生',
    '三好学生', '优秀毕业生',
    '竞赛', '比赛', '大赛', '选拔', '报名',
    '获奖', '奖金',
]

MEDIUM_KEYWORDS = [
    '学术', '科研', '论文', '课题', '调研', '报告',
    '讲座', '论坛', '研讨会', '学术交流',
    '实习', '招聘', '就业', '简历', '面试',
    '家教', '辅导', '兼职', '助教',
    '互联网+', '节能减排', '机器人', '编程',
    '英语竞赛', '翻译', '外研社',
    '创新创业', '科创', '挑战',
    '优秀', '评选', '评审',
]

EXCLUDE_KEYWORDS = [
    '献血', '义工', '志愿者', '捐', '卫生',
    '防疫', '核酸', '疫苗',
    '后勤', '水电', '宿舍', '食堂', '维修',
]

CATEGORY_MAP = {
    '竞赛': ['竞赛', '比赛', '大赛', '挑战杯', '大创', '互联网+', '节能减排', '数学建模', '物理竞赛', '数学竞赛', '科学竞赛', '英语竞赛', '外研社', '机器人', '编程'],
    '奖学金': ['奖学金', '国家奖学金', '励志奖学金', '优秀学生', '三好学生'],
    '教学相关': ['师范', '教学技能', '讲课比赛', '微课', '模拟课堂', '教师资格', '教育实习', '家教', '辅导', '助教'],
    '就业实习': ['实习', '招聘', '就业', '简历', '面试', '兼职'],
    '学术科研': ['学术', '科研', '论文', '课题', '调研', '讲座', '论坛', '研讨会'],
    '评选荣誉': ['优秀', '评选', '评审', '获奖', '奖金', '优秀毕业生'],
}


def score_article(article):
    """标题快速评分"""
    title = article.get('title', '')
    score = 0
    reasons = []

    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            score -= 50
            reasons.append(f'排除:{kw}')

    for kw in HIGH_KEYWORDS:
        if kw in title:
            score += 40
            reasons.append(f'高:{kw}')

    for kw in MEDIUM_KEYWORDS:
        if kw in title:
            score += 15
            reasons.append(f'中:{kw}')

    return score, reasons


def get_tags(article):
    full_text = article.get('title', '') + ' ' + article.get('content', '')
    tags = []
    for tag, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in full_text:
                if tag not in tags:
                    tags.append(tag)
                break
    return tags or ['其他']


def fetch_details(articles, config, min_score=30):
    """只对命中的文章爬详情页"""
    # 评分
    for a in articles:
        a['relevance_score'], a['match_reasons'] = score_article(a)

    # 筛选
    relevant = [a for a in articles if a['relevance_score'] >= min_score]
    relevant.sort(key=lambda x: x['relevance_score'], reverse=True)

    print(f"\n  筛选: {len(articles)} → {len(relevant)} 条相关")

    # 爬详情
    for i, a in enumerate(relevant, 1):
        print(f"  详情 [{i}/{len(relevant)}] {a['title'][:35]}...")
        html = fetch_page(a['url'])
        if html:
            a['content'] = parse_article_content(html)
            a.update(extract_structured_info(a, a['content']))
        else:
            a['content_fetch_failed'] = True
        a['tags'] = get_tags(a)
        if a.get('parsed_date'):
            a['publish_date'] = a['parsed_date'].strftime('%Y-%m-%d')
        else:
            a['publish_date'] = a.get('date_str', '')
        time.sleep(0.5)

    return relevant


def save_results(relevant, output_dir):
    """保存筛选结果"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    date_str = datetime.now().strftime('%Y-%m-%d')

    # JSON
    json_path = os.path.join(output_dir, 'useful_filtered.json')
    json_data = {
        '筛选时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '筛选结果数': len(relevant),
        '通知列表': [{
            'title': a.get('title', ''),
            'url': a.get('url', ''),
            'publish_date': a.get('publish_date', ''),
            'source_site': a.get('source_site', ''),
            'deadline': a.get('deadline'),
            'relevance_score': a.get('relevance_score', 0),
            'tags': a.get('tags', []),
            'summary': a.get('summary', '')[:200],
            'location': a.get('location'),
            'category': a.get('category', ''),
        } for a in relevant]
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # 文本
    txt_path = os.path.join(output_dir, 'useful_filtered.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"校园通知筛选 — {date_str}\n共 {len(relevant)} 条\n{'='*50}\n\n")
        by_tag = {}
        for a in relevant:
            for t in a.get('tags', ['其他']):
                by_tag.setdefault(t, []).append(a)
        for tag, items in by_tag.items():
            f.write(f"\n【{tag}】({len(items)}条)\n{'─'*40}\n")
            for a in items:
                f.write(f"  📌 {a.get('title','')}\n")
                f.write(f"     {a.get('source_site','')} | {a.get('publish_date','')}\n")
                if a.get('deadline'):
                    f.write(f"     ⏰ 截止: {a['deadline']}\n")
                if a.get('summary'):
                    f.write(f"     {a['summary'][:100]}\n")
                f.write(f"     🔗 {a.get('url','')}\n\n")

    print(f"  JSON: {json_path}")
    print(f"  文本: {txt_path}")
    return json_path, txt_path


def build_feishu_message(relevant):
    """构建飞书推送消息"""
    lines = []
    lines.append("🦋 校园通知筛选")
    lines.append(f"共 {len(relevant)} 条（最近7天）\n")

    # 按分类分组
    by_tag = {}
    for a in relevant:
        for t in a.get('tags', ['其他']):
            if t not in by_tag:
                by_tag[t] = []
            by_tag[t].append(a)

    for tag in ['竞赛', '奖学金', '教学相关', '就业实习', '学术科研', '评选荣誉']:
        items = by_tag.get(tag, [])
        if not items:
            continue
        lines.append(f"【{tag}】{len(items)}条")
        for a in items[:5]:  # 每类最多5条
            title = a.get('title', '')[:35]
            date = a.get('publish_date', '')
            deadline = a.get('deadline', '')
            url = a.get('url', '')
            dl_str = f" ⏰{deadline}" if deadline else ""
            lines.append(f"• {title}")
            lines.append(f"  {a.get('source_site','')} | {date}{dl_str}")
            lines.append(f"  {url}")
        lines.append("")

    return '\n'.join(lines).strip()


def push_feishu(relevant):
    """推送到飞书"""
    try:
        import subprocess, sys
        msg = build_feishu_message(relevant)
        send_safe = "C:\\Users\\wang\\.copaw\\workspaces\\default\\skills\\feishu-sender\\send_safe.py"
        result = subprocess.run(
            [sys.executable, send_safe, '--text', msg],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("  📤 飞书推送成功")
        else:
            print("  ⚠️ 飞书推送失败:", result.stderr[-200:])
    except Exception as e:
        print("  ⚠️ 飞书推送异常:", str(e))


# ── 主流程 ──

def run(days=7, min_score=30, output_dir=None, push=True):
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')

    config_path = os.path.join(os.path.dirname(__file__), 'sites_config.json')
    config = load_config(config_path)

    print(f"[{datetime.now().strftime('%H:%M')}] Phase 1: 爬取列表（{days}天）...")
    all_articles = scrape_all_lists(config, days)
    print(f"  共 {len(all_articles)} 条\n")

    print("Phase 2: 筛选相关性 + 爬详情...")
    relevant = fetch_details(all_articles, config, min_score)

    if relevant:
        save_results(relevant, output_dir)
        print(f"\n✅ 完成！{len(relevant)} 条有用通知")
        for a in relevant[:5]:
            tags = ', '.join(a.get('tags', []))
            print(f"  [{tags}] {a.get('title','')[:45]}")
        if push:
            print()
            push_feishu(relevant)
    else:
        print("\n  本次未筛到相关通知，飞书跳过")

    return relevant


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--min-score', type=float, default=30)
    parser.add_argument('--output', default=None)
    parser.add_argument('--no-push', action='store_true', help='跳过飞书推送')
    args = parser.parse_args()
    run(args.days, args.min_score, args.output, push=not args.no_push)

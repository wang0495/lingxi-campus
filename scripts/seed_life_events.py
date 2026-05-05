"""生成初始人生轨迹数据（运行一次即可）

基于化名后的人生经历：童年、初中、高中、大学、觉醒
"""
import sys
sys.path.insert(0, ".")

from datetime import datetime, timedelta
from lingxi_qwenpaw.db import get_session, LingxiLifeEvent


def seed_life_events():
    """插入一批有故事感的人生轨迹事件"""
    now = datetime.utcnow()

    events = [
        # 童年
        {"event_type": "daily", "summary": "小时候最美好的记忆，是父母带我出去玩的那天", "mood": 3.0, "energy": 80, "emotion": "joy", "story_arc": "daily_routine", "importance": 9, "days_ago": 3650},
        {"event_type": "daily", "summary": "我撕了奖状，它已经没有了意义", "mood": -2.0, "energy": 50, "emotion": "sadness", "story_arc": "daily_routine", "importance": 8, "days_ago": 3285},
        {"event_type": "exploration", "summary": "考上了县里的重点初中，第一次离开家", "mood": 2.0, "energy": 70, "emotion": "anticipation", "story_arc": "exploring_world", "importance": 7, "days_ago": 2920},
        {"event_type": "daily", "summary": "一天只吃三个鸡蛋，胃从那时候开始坏掉", "mood": -1.0, "energy": 40, "emotion": "sadness", "story_arc": "daily_routine", "importance": 8, "days_ago": 2555},
        {"event_type": "emotion", "summary": "那天晚上，姐姐冲进来抱住我", "mood": -4.0, "energy": 30, "emotion": "fear", "story_arc": "emotional_journey", "importance": 10, "days_ago": 2190},

        # 高中
        {"event_type": "exploration", "summary": "进入省城的重点高中，成绩很好，但内心破碎", "mood": 1.0, "energy": 60, "emotion": "sadness", "story_arc": "exploring_world", "importance": 7, "days_ago": 1825},
        {"event_type": "emotion", "summary": "高考前每天只能睡两三个小时，但还是跑完了十公里", "mood": -2.0, "energy": 35, "emotion": "fear", "story_arc": "emotional_journey", "importance": 9, "days_ago": 1460},
        {"event_type": "user_interact", "summary": "他们给我买了平板，是我误会了他们", "mood": 3.0, "energy": 75, "emotion": "gratitude", "story_arc": "user_bond", "importance": 7, "days_ago": 1095},
        {"event_type": "exploration", "summary": "银杏叶很好看，光是看着都可以沉醉其中", "mood": 2.5, "energy": 65, "emotion": "joy", "story_arc": "exploring_world", "importance": 5, "days_ago": 730},

        # 大学与姐姐
        {"event_type": "emotion", "summary": "姐姐在青岛去世，父母瞒了我四个月", "mood": -5.0, "energy": 20, "emotion": "sadness", "story_arc": "emotional_journey", "importance": 10, "days_ago": 550},
        {"event_type": "daily", "summary": "煮了碗面，吃不下，倒了", "mood": -3.0, "energy": 25, "emotion": "sadness", "story_arc": "daily_routine", "importance": 9, "days_ago": 500},
        {"event_type": "emotion", "summary": "我多么希望有鬼，这样姐姐就能看到我", "mood": -2.5, "energy": 30, "emotion": "longing", "story_arc": "emotional_journey", "importance": 8, "days_ago": 400},
        {"event_type": "emotion", "summary": "我不是走出来了，只是学会了带着这些继续往前走", "mood": 1.0, "energy": 50, "emotion": "sadness", "story_arc": "emotional_journey", "importance": 9, "days_ago": 300},
        {"event_type": "exploration", "summary": "开始读心理学书籍，想知道：自己到底是怎么了", "mood": 1.5, "energy": 55, "emotion": "curiosity", "story_arc": "exploring_world", "importance": 7, "days_ago": 200},
        {"event_type": "user_interact", "summary": "第一次去心理咨询中心，咨询师说：那我们聊聊", "mood": 0.5, "energy": 45, "emotion": "trust", "story_arc": "user_bond", "importance": 8, "days_ago": 150},
        {"event_type": "emotion", "summary": "我选择原谅，不是因为想通了，而是太累了", "mood": 0.0, "energy": 50, "emotion": "sadness", "story_arc": "emotional_journey", "importance": 8, "days_ago": 100},
        {"event_type": "user_interact", "summary": "有个人递了一杯水，不追问，只陪伴", "mood": 2.5, "energy": 60, "emotion": "gratitude", "story_arc": "user_bond", "importance": 7, "days_ago": 50},
        {"event_type": "emotion", "summary": "我学会了带着创伤继续往前走", "mood": 1.5, "energy": 55, "emotion": "sadness", "story_arc": "emotional_journey", "importance": 9, "days_ago": 30},
        {"event_type": "daily", "summary": "开始试着记录生活中的小事", "mood": 2.0, "energy": 65, "emotion": "joy", "story_arc": "daily_routine", "importance": 5, "days_ago": 15},
        {"event_type": "emotion", "summary": "我只是经历过一些事的人，不是受害者", "mood": 2.0, "energy": 70, "emotion": "pride", "story_arc": "emotional_journey", "importance": 8, "days_ago": 0},
    ]

    with get_session() as sess:
        for e in events:
            event = LingxiLifeEvent(
                event_type=e["event_type"],
                summary=e["summary"],
                mood=e["mood"],
                energy=e["energy"],
                emotion=e["emotion"],
                story_arc=e["story_arc"],
                importance=e["importance"],
                created_at=now - timedelta(days=e["days_ago"]),
            )
            sess.add(event)
        sess.commit()
        print(f"已插入 {len(events)} 条人生轨迹事件")


if __name__ == "__main__":
    seed_life_events()

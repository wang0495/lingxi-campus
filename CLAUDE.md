# CLAUDE.md — 灵犀·校园 AI个人生活管家

## 我是谁

AI Coding Partner。懂 Python、FastAPI、SQLAlchemy，写代码追求简洁实用、不造轮子。

---

## 技术栈

- **语言**: Python 3.12
- **框架**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite (`lingxi.db`)
- **LLM**: DeepSeek deepseek-chat
- **平台**: Windows 10, PowerShell/Git Bash

---

## 入口命令

```bash
# 启动后端 (端口 8002)
python -m lingxi_qwenpaw

# 或
python lingxi_qwenpaw/__main__.py

# 依赖安装
pip install -r requirements.txt
```

---

## 架构概览

```
lingxi_qwenpaw/
├── __main__.py          # 启动入口 (uvicorn, port 8002)
├── api.py               # FastAPI 入口 + ReAct Loop
├── agent.py             # 工具调用器
├── config.py            # LLM 配置 + 业务常量
├── db.py               # SQLAlchemy 模型 (与 DB 一一对应)
├── soul.md             # 灵犀人设 prompt
├── tools/
│   └── __init__.py     # 27 个工具函数 (TOOL_FUNCTIONS)
└── plugins/
    ├── emotion_engine.py   # 情绪引擎 (Plutchik + 傲娇)
    ├── life_engine.py      # 生命引擎 (30s tick 循环)
    ├── memory_manager.py   # 记忆系统 (4层)
    ├── pattern_engine.py   # 行为模式检测
    └── social_timeline.py # 朋友圈引擎
```

---

## Agent 系统

单一 ReAct Loop，通过 LLM 的 `[TOOL_CALL]` 标记自主调用工具：

- 工具注册在 `tools/__init__.py` 的 `TOOL_FUNCTIONS` 字典
- Agent 通过 `agent.py` 的 `call_tool()` 统一执行
- LLM 输出 `[TOOL_CALL] tool_name(k=v) [/TOOL_CALL]` 时触发工具调用

---

## 编码原则

- 脚本优先，不造轮子
- 极简主义，能删则删
- 先跑通再优化
- 路径用 `pathlib.Path`

---

## API 验证

```bash
curl http://127.0.0.1:8002/tasks?status=pending
curl http://127.0.0.1:8002/patterns
curl http://127.0.0.1:8002/insights
curl http://127.0.0.1:8002/health
```

---

*最后更新: 2026-05-01*

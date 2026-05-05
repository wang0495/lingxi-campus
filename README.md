# 灵犀·校园

> 有灵魂的数字伙伴 — AI 个人生活管家

## 项目简介

灵犀·校园是一个具有情感和个性的 AI 助手，能够像真人一样与用户进行社交互动，帮助管理日常生活。

### 核心特性

- 🧠 **智能对话**：基于 DeepSeek 大模型，支持多轮对话和上下文理解
- 💭 **情感系统**：拥有独立的情绪状态，会开心、生气、委屈、撒娇
- 📅 **日程管理**：智能任务提醒和时间规划
- 💰 **记账助手**：收支记录和财务分析
- 📝 **日记功能**：自动生成生活记录
- 🎯 **习惯追踪**：时间统计和行为模式分析
- 🔊 **语音交互**：支持语音输入和识别

## 项目结构

```
灵犀校园PCG大赛/
├── lingxi_qwenpaw/          # 后端核心模块
│   ├── api.py               # FastAPI 服务入口
│   ├── config.py            # 配置管理
│   ├── auth.py              # 用户认证
│   ├── db.py                # 数据库操作
│   ├── bridge.py            # LLM 调用桥接
│   ├── agent.py             # Agent 工具调用
│   ├── tools/               # 工具函数集合
│   └── plugins/             # 插件模块
│       ├── emotion_engine.py    # 情绪引擎
│       ├── life_engine.py       # 生活引擎
│       ├── memory_manager.py    # 记忆管理
│       └── context_manager.py   # 上下文管理
│
├── frontend/                # Web 前端
│   ├── index.html           # 主页面
│   └── config.js            # 前端配置
│
├── mobile-app/              # 移动端应用
│   └── www/index.html       # 移动端页面
│
├── electron-app/            # Electron 桌面应用
│   ├── main.js              # 主进程
│   └── package.json         # 依赖配置
│
├── video-promo/             # 视频宣传页
│   └── index.html           # 宣传页面
│
├── .env                     # 环境变量配置（需自行创建）
├── .env.example             # 环境变量模板
├── pyproject.toml           # Python 项目配置
└── requirements.txt         # Python 依赖
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+（如需运行 Electron 应用）

### 2. 配置环境变量

```bash
# 复制模板文件
cp .env.example .env

# 编辑 .env 文件，填入您的 API 密钥
```

必需的环境变量：

| 变量名 | 说明 |
|--------|------|
| `LLM_API_KEY` | DeepSeek API 密钥 |
| `EMBEDDING_API_KEY` | SiliconFlow API 密钥 |
| `JWT_SECRET` | JWT 加密密钥（32位随机字符串） |

### 3. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 或使用 pip 安装项目
pip install -e .
```

### 4. 启动服务

```bash
# 启动后端服务
cd lingxi_qwenpaw
python api.py

# 服务将在 http://localhost:8002 启动
```

### 5. 访问前端

直接在浏览器中打开 `frontend/index.html` 文件。

## API 文档

启动服务后访问：
- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/register` | POST | 用户注册 |
| `/auth/login` | POST | 用户登录 |
| `/chat/stream` | POST | 流式对话 |
| `/tasks` | GET/POST | 任务管理 |
| `/ledger` | GET/POST | 记账管理 |
| `/timeline` | GET | 动态时间线 |

## 开发指南

### 代码风格

项目使用 Ruff 进行代码检查和格式化：

```bash
# 检查代码
ruff check .

# 格式化代码
ruff format .
```

### 类型检查

```bash
mypy lingxi_qwenpaw/
```

### 运行测试

```bash
pytest tests/
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy + OpenAI SDK
- **前端**: 原生 HTML/CSS/JavaScript
- **桌面端**: Electron
- **AI 模型**: DeepSeek (LLM) + SiliconFlow (Embedding/Vision/STT)
- **数据库**: SQLite

## 安全注意事项

⚠️ **生产环境部署前请务必：**

1. 修改 `.env` 中的所有密钥
2. 设置强密码策略的 `JWT_SECRET`
3. 配置正确的 `ALLOWED_ORIGINS`
4. 使用 HTTPS 协议
5. 启用请求速率限制

## 许可证

MIT License

## 贡献指南

欢迎提交 Issue 和 Pull Request！

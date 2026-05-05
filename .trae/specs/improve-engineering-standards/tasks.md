# Tasks

## 阶段一：日志系统重构

- [x] Task 1: 创建日志配置模块
  - [x] SubTask 1.1: 创建 `lingxi_qwenpaw/logger.py`，配置标准 logging
  - [x] SubTask 1.2: 支持控制台和文件输出
  - [x] SubTask 1.3: 支持环境变量控制日志级别

- [x] Task 2: 替换所有 print 语句为 logging
  - [x] SubTask 2.1: 替换 `api.py` 中的 print 语句
  - [x] SubTask 2.2: 替换 `bridge.py` 中的 print 语句
  - [x] SubTask 2.3: 替换 `auth.py` 中的 print 语句
  - [x] SubTask 2.4: 替换 `__main__.py` 中的 print 语句

## 阶段二：错误处理改进

- [x] Task 3: 创建自定义异常类
  - [x] SubTask 3.1: 创建 `lingxi_qwenpaw/exceptions.py`
  - [x] SubTask 3.2: 定义 LingxiError 基类和具体异常类型

- [x] Task 4: 重构错误处理
  - [x] SubTask 4.1: 重构 `db.py` 中的错误处理
  - [x] SubTask 4.2: 重构 `tools/__init__.py` 中的错误处理
  - [x] SubTask 4.3: 重构 `api.py` 中的错误处理

## 阶段三：API 增强

- [x] Task 5: 添加速率限制中间件
  - [x] SubTask 5.1: 创建 `lingxi_qwenpaw/middleware/rate_limit.py`
  - [x] SubTask 5.2: 在 api.py 中注册中间件

- [x] Task 6: 添加健康检查端点
  - [x] SubTask 6.1: 在 api.py 添加 `/health` 端点
  - [x] SubTask 6.2: 返回服务状态和数据库连接状态

- [x] Task 7: 添加请求追踪 ID
  - [x] SubTask 7.1: 创建 `lingxi_qwenpaw/middleware/request_id.py`
  - [x] SubTask 7.2: 在日志中包含请求 ID

## 阶段四：测试覆盖

- [x] Task 8: 添加单元测试
  - [x] SubTask 8.1: 创建 `tests/test_api.py` 测试 API 端点
  - [x] SubTask 8.2: 创建 `tests/test_db.py` 测试数据库操作
  - [x] SubTask 8.3: 创建 `tests/test_bridge.py` 测试桥接层
  - [x] SubTask 8.4: 创建 `tests/test_tools.py` 测试工具函数

- [x] Task 9: 配置测试覆盖率报告
  - [x] SubTask 9.1: 更新 pyproject.toml 添加覆盖率配置
  - [x] SubTask 9.2: 确保核心模块覆盖率 >= 50%

## 阶段五：CI/CD 完善

- [x] Task 10: 添加 CI 工作流
  - [x] SubTask 10.1: 创建 `.github/workflows/ci.yml`
  - [x] SubTask 10.2: 配置代码检查（ruff、mypy）
  - [x] SubTask 10.3: 配置自动测试

# Task Dependencies

- Task 2 依赖 Task 1（需要先有日志模块）
- Task 4 依赖 Task 3（需要先有异常类）
- Task 5、6、7 可并行执行
- Task 8 依赖 Task 1-4（需要日志和错误处理完成）
- Task 9 依赖 Task 8（需要先有测试）
- Task 10 依赖 Task 8、9（需要测试通过）

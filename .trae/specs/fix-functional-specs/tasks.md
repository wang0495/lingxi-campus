# Tasks

## 阶段一：认证接口安全改进

- [x] Task 1: 修改认证接口使用请求体
  - [x] SubTask 1.1: 创建 LoginRequest 和 RegisterRequest Pydantic 模型
  - [x] SubTask 1.2: 修改 /auth/login 接口使用请求体
  - [x] SubTask 1.3: 修改 /auth/register 接口使用请求体
  - [x] SubTask 1.4: 更新相关测试

- [x] Task 2: 实现 Token 刷新机制
  - [x] SubTask 2.1: 缩短访问令牌有效期为 30 分钟
  - [x] SubTask 2.2: 创建刷新令牌生成和验证函数
  - [x] SubTask 2.3: 添加 /auth/refresh 端点
  - [x] SubTask 2.4: 更新前端 Token 刷新逻辑

## 阶段二：API 响应格式统一

- [x] Task 3: 统一错误响应格式
  - [x] SubTask 3.1: 创建统一响应模型 ApiResponse 和 ErrorResponse
  - [x] SubTask 3.2: 修改所有接口使用统一响应格式
  - [x] SubTask 3.3: 更新全局异常处理器
  - [x] SubTask 3.4: 更新 API 文档示例

## 阶段三：数据库优化

- [x] Task 4: 添加数据库索引
  - [x] SubTask 4.1: 为 Task 模型添加 (user_id, status) 索引
  - [x] SubTask 4.2: 为 Task 模型添加 (user_id, deadline) 索引
  - [x] SubTask 4.3: 为 LedgerRecord 模型添加 (user_id, date) 索引
  - [x] SubTask 4.4: 为 MemoryEntry 模型添加 (user_id, layer) 索引

- [x] Task 5: 完善字段约束
  - [x] SubTask 5.1: 为 Task.urgency 添加范围约束 (1-5)
  - [x] SubTask 5.2: 为 LedgerRecord.amount 添加非负约束
  - [x] SubTask 5.3: 为各模型添加 updated_at 字段

## 阶段四：工具函数规范

- [x] Task 6: 统一工具函数返回值格式
  - [x] SubTask 6.1: 创建统一返回值辅助函数
  - [x] SubTask 6.2: 修改所有工具函数使用统一格式
  - [x] SubTask 6.3: 更新工具函数测试

- [x] Task 7: 添加输入验证
  - [x] SubTask 7.1: 为 create_task 添加 content 长度验证
  - [x] SubTask 7.2: 为 add_ledger 添加 amount 非负验证
  - [x] SubTask 7.3: 为日期解析添加边界情况处理

# Task Dependencies

- Task 2 依赖 Task 1（需要先有认证接口）
- Task 3 可独立执行
- Task 4、5 可并行执行
- Task 6、7 可并行执行
- Task 7 依赖 Task 6（需要先有统一返回格式）

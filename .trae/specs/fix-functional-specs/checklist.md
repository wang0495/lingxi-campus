# 功能规范修复检查清单

## 认证接口安全

- [x] LoginRequest Pydantic 模型创建完成
- [x] RegisterRequest Pydantic 模型创建完成
- [x] /auth/login 接口使用请求体
- [x] /auth/register 接口使用请求体
- [x] 访问令牌有效期为 30 分钟
- [x] 刷新令牌有效期为 7 天
- [x] /auth/refresh 端点可用
- [x] 前端 Token 刷新逻辑已更新

## API 响应格式

- [x] ApiResponse 模型创建完成
- [x] ErrorResponse 模型创建完成
- [x] 所有接口使用统一响应格式
- [x] 全局异常处理器返回统一格式
- [x] API 文档包含响应示例

## 数据库优化

- [x] Task(user_id, status) 索引已添加
- [x] Task(user_id, deadline) 索引已添加
- [x] LedgerRecord(user_id, date) 索引已添加
- [x] MemoryEntry(user_id, layer) 索引已添加
- [x] Task.urgency 有范围约束 (1-5)
- [x] LedgerRecord.amount 有非负约束
- [x] 各模型有 updated_at 字段

## 工具函数规范

- [x] 统一返回值辅助函数创建完成
- [x] 所有工具函数使用统一返回格式
- [x] create_task 有 content 长度验证
- [x] add_ledger 有 amount 非负验证
- [x] 日期解析处理边界情况
- [x] 工具函数测试已更新

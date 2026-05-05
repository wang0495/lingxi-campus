# 功能规范修复 Spec

## Why
项目存在多处功能规范问题：登录接口使用 Query 参数传递密码、错误响应格式不统一、数据库缺少索引、Token 有效期过长等。这些问题会导致安全风险、性能问题和用户体验不佳。

## What Changes
- 登录/注册接口改用请求体传递参数
- 统一 API 错误响应格式
- 添加数据库索引优化查询性能
- 缩短 Token 有效期并实现刷新机制
- 完善字段约束和输入验证
- 统一工具函数返回值格式

## Impact
- Affected specs: 认证系统、API 接口、数据库模型、工具函数
- Affected code:
  - `lingxi_qwenpaw/api.py` - 修改认证接口、统一错误格式
  - `lingxi_qwenpaw/auth.py` - Token 有效期、刷新机制
  - `lingxi_qwenpaw/db.py` - 添加索引、完善约束
  - `lingxi_qwenpaw/tools/__init__.py` - 统一返回格式、输入验证

## ADDED Requirements

### Requirement: 安全的认证接口
系统 SHALL 使用请求体传递认证参数，而非 URL Query 参数。

#### Scenario: 登录请求
- **WHEN** 用户发送 POST /auth/login 请求
- **THEN** 系统应从请求体读取 username 和 password

#### Scenario: 注册请求
- **WHEN** 用户发送 POST /auth/register 请求
- **THEN** 系统应从请求体读取用户信息

### Requirement: 统一的错误响应格式
系统 SHALL 返回统一格式的错误响应。

#### Scenario: API 错误
- **WHEN** API 请求失败
- **THEN** 响应应包含 success、error_code、message、details 字段

### Requirement: Token 刷新机制
系统 SHALL 提供短期访问令牌和长期刷新令牌。

#### Scenario: Token 过期
- **WHEN** 访问令牌过期
- **THEN** 用户可使用刷新令牌获取新的访问令牌

### Requirement: 数据库索引优化
系统 SHALL 为高频查询字段添加数据库索引。

#### Scenario: 任务查询
- **WHEN** 查询用户的待办任务
- **THEN** 系统应使用 (user_id, status) 组合索引

### Requirement: 输入验证
系统 SHALL 验证所有工具函数的输入参数。

#### Scenario: 任务创建验证
- **WHEN** 创建任务时 content 为空或过长
- **THEN** 系统应返回验证错误

## MODIFIED Requirements

### Requirement: Token 有效期
访问令牌有效期从 7 天修改为 30 分钟，刷新令牌有效期为 7 天。

### Requirement: 工具函数返回值
所有工具函数返回值统一为 `{"success": bool, "content": str, "data": dict}` 格式。

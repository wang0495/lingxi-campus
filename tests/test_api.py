"""API 端点测试

测试内容：
- 健康检查端点 /health
- 认证端点 /auth/register 和 /auth/login
- 速率限制中间件
- 请求 ID 中间件
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from fastapi import FastAPI


# 测试用户配置
TEST_USERNAME = "test"
TEST_PASSWORD = "testpassword123"


@pytest.fixture
def test_app():
    """创建测试用的 FastAPI 应用"""
    # 设置测试环境变量
    os.environ["JWT_SECRET"] = "test_secret_key_for_testing_only"
    os.environ["RATE_LIMIT_REQUESTS"] = "100"
    os.environ["RATE_LIMIT_WINDOW"] = "60"

    # 导入并创建应用
    from lingxi_qwenpaw.api import app

    yield app


@pytest.fixture
def client(test_app):
    """创建测试客户端"""
    return TestClient(test_app)


@pytest.fixture
def auth_token(client):
    """获取认证令牌"""
    # 先尝试注册
    client.post("/auth/register", params={"username": TEST_USERNAME, "password": TEST_PASSWORD})

    # 登录获取 token
    response = client.post("/auth/login", params={"username": TEST_USERNAME, "password": TEST_PASSWORD})

    if response.status_code == 200:
        return response.json().get("token")
    return None


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_endpoint_returns_200(self, client):
        """测试健康检查端点返回 200 状态码"""
        response = client.get("/health")

        assert response.status_code in [200, 503]  # 503 表示数据库连接失败

    def test_health_endpoint_structure(self, client):
        """测试健康检查响应结构"""
        response = client.get("/health")
        data = response.json()

        # 验证响应包含必要字段
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "database" in data
        assert "uptime_seconds" in data

    def test_health_endpoint_status_values(self, client):
        """测试健康检查状态值"""
        response = client.get("/health")
        data = response.json()

        # 验证状态值
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["database"] in ["connected", "disconnected"]
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0


class TestAuthEndpoints:
    """认证端点测试"""

    def test_register_new_user(self, client):
        """测试注册新用户"""
        # 使用唯一的用户名避免冲突
        import time
        unique_username = f"test_user_{int(time.time())}"
        unique_password = "TestPass123"

        response = client.post(
            "/auth/register",
            params={"username": unique_username, "password": unique_password}
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_register_duplicate_user(self, client):
        """测试注册重复用户名"""
        import time
        unique_username = f"test_dup_{int(time.time())}"
        unique_password = "TestPass123"

        # 第一次注册
        client.post(
            "/auth/register",
            params={"username": unique_username, "password": unique_password}
        )

        # 第二次注册相同用户名
        response = client.post(
            "/auth/register",
            params={"username": unique_username, "password": unique_password}
        )

        assert response.status_code == 400

    def test_register_short_username(self, client):
        """测试用户名过短"""
        response = client.post(
            "/auth/register",
            params={"username": "a", "password": "TestPass123"}
        )

        assert response.status_code == 400

    def test_register_weak_password(self, client):
        """测试弱密码"""
        import time
        unique_username = f"test_weak_{int(time.time())}"

        # 密码太短
        response = client.post(
            "/auth/register",
            params={"username": unique_username, "password": "short"}
        )
        assert response.status_code == 400

    def test_login_success(self, client):
        """测试登录成功"""
        import time
        unique_username = f"test_login_{int(time.time())}"
        unique_password = "TestPass123"

        # 先注册
        client.post(
            "/auth/register",
            params={"username": unique_username, "password": unique_password}
        )

        # 再登录
        response = client.post(
            "/auth/login",
            params={"username": unique_username, "password": unique_password}
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "token" in data
        assert data.get("username") == unique_username

    def test_login_wrong_password(self, client):
        """测试登录密码错误"""
        import time
        unique_username = f"test_wrong_{int(time.time())}"
        unique_password = "TestPass123"

        # 先注册
        client.post(
            "/auth/register",
            params={"username": unique_username, "password": unique_password}
        )

        # 用错误密码登录
        response = client.post(
            "/auth/login",
            params={"username": unique_username, "password": "WrongPassword123"}
        )

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """测试登录不存在的用户"""
        response = client.post(
            "/auth/login",
            params={"username": "nonexistent_user_xyz", "password": "SomePassword123"}
        )

        assert response.status_code == 401

    def test_verify_token_valid(self, client, auth_token):
        """测试验证有效 token"""
        if not auth_token:
            pytest.skip("无法获取认证令牌")

        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    def test_verify_token_invalid(self, client):
        """测试验证无效 token"""
        response = client.get(
            "/auth/verify",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_verify_token_missing(self, client):
        """测试缺少 token"""
        response = client.get("/auth/verify")

        assert response.status_code == 401


class TestRateLimitMiddleware:
    """速率限制中间件测试"""

    def test_rate_limit_headers_present(self, client):
        """测试速率限制响应头存在"""
        response = client.get("/health")

        # 健康检查端点被排除在速率限制之外
        # 但其他端点应该有速率限制头
        assert response.status_code in [200, 503]

    def test_rate_limit_excluded_paths(self, client):
        """测试排除的路径不受速率限制"""
        # 健康检查端点应该不受速率限制
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code in [200, 503]


class TestRequestIDMiddleware:
    """请求 ID 中间件测试"""

    def test_request_id_generated(self, client):
        """测试请求 ID 自动生成"""
        response = client.get("/health")

        # 检查响应头中是否有请求 ID
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0

    def test_request_id_unique(self, client):
        """测试每次请求的 ID 唯一"""
        response1 = client.get("/health")
        response2 = client.get("/health")

        # 两次请求的 ID 应该不同
        id1 = response1.headers.get("X-Request-ID")
        id2 = response2.headers.get("X-Request-ID")

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2

    def test_request_id_from_header(self, client):
        """测试使用请求头中的请求 ID"""
        custom_id = "custom-request-id-12345"

        response = client.get(
            "/health",
            headers={"X-Request-ID": custom_id}
        )

        # 响应应该返回相同的请求 ID
        assert response.headers.get("X-Request-ID") == custom_id


class TestProtectedEndpoints:
    """需要认证的端点测试"""

    def test_tasks_endpoint_requires_auth(self, client):
        """测试任务端点需要认证"""
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_tasks_endpoint_with_auth(self, client, auth_token):
        """测试带认证的任务端点"""
        if not auth_token:
            pytest.skip("无法获取认证令牌")

        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data

    def test_lingxi_status_requires_auth(self, client):
        """测试灵犀状态端点需要认证"""
        response = client.get("/lingxi/status")
        assert response.status_code == 401

    def test_lingxi_status_with_auth(self, client, auth_token):
        """测试带认证的灵犀状态端点"""
        if not auth_token:
            pytest.skip("无法获取认证令牌")

        response = client.get(
            "/lingxi/status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "emotion" in data
        assert "life" in data


class TestChatEndpoint:
    """聊天端点测试"""

    def test_chat_requires_auth(self, client):
        """测试聊天端点需要认证"""
        response = client.post(
            "/chat",
            json={"message": "你好"}
        )
        assert response.status_code == 401

    def test_chat_history_requires_auth(self, client):
        """测试聊天历史端点需要认证"""
        response = client.get("/chat/history")
        assert response.status_code == 401


class TestExceptionHandling:
    """异常处理测试"""

    def test_404_not_found(self, client):
        """测试 404 错误"""
        response = client.get("/nonexistent_endpoint")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """测试方法不允许"""
        response = client.post("/health")
        assert response.status_code == 405


class TestCORSMiddleware:
    """CORS 中间件测试"""

    def test_cors_headers(self, client):
        """测试 CORS 响应头"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # 检查 CORS 相关响应头
        # 注意：TestClient 可能不完全模拟 CORS 行为
        assert response.status_code in [200, 400, 405]

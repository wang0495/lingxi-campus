"""
速率限制中间件

基于 IP 地址的请求速率限制，使用内存存储实现。
支持环境变量配置限制参数，返回标准的 RateLimit 响应头。
"""

import os
import time
import threading
from typing import Callable, Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from lingxi_qwenpaw.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件

    功能：
    - 基于 IP 地址限制请求频率
    - 使用内存字典存储请求记录
    - 线程安全（使用 threading.Lock）
    - 支持环境变量配置
    - 返回标准 RateLimit 响应头

    环境变量：
    - RATE_LIMIT_REQUESTS: 时间窗口内最大请求数（默认 60）
    - RATE_LIMIT_WINDOW: 时间窗口秒数（默认 60）
    """

    def __init__(self, app, **kwargs):
        """
        初始化速率限制中间件

        参数：
            app: FastAPI 应用实例
        """
        super().__init__(app, **kwargs)

        # 从环境变量读取配置，使用默认值作为后备
        self.max_requests = int(os.environ.get("RATE_LIMIT_REQUESTS", "60"))
        self.window_seconds = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

        # 内存存储：{ip_address: (request_count, window_start_time)}
        # 使用字典存储每个 IP 的请求记录
        self._store: Dict[str, Tuple[int, float]] = {}

        # 线程锁，确保多线程环境下的数据安全
        self._lock = threading.Lock()

        # 排除的端点列表（不进行速率限制）
        self.excluded_paths = {"/health"}

        logger.info(
            f"速率限制中间件已初始化: "
            f"max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}"
        )

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端 IP 地址

        优先从代理头（X-Forwarded-For, X-Real-IP）获取真实 IP，
        否则使用直接连接的客户端地址。

        参数：
            request: FastAPI 请求对象

        返回：
            客户端 IP 地址字符串
        """
        # 尝试从 X-Forwarded-For 头获取（代理场景）
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For 可能包含多个 IP，取第一个（原始客户端）
            return forwarded_for.split(",")[0].strip()

        # 尝试从 X-Real-IP 头获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # 使用直接连接的客户端地址
        if request.client:
            return request.client.host

        # 无法获取 IP 时使用默认值
        return "unknown"

    def _check_rate_limit(self, client_ip: str) -> Tuple[bool, int, int, int]:
        """
        检查是否超过速率限制

        参数：
            client_ip: 客户端 IP 地址

        返回：
            元组 (is_allowed, remaining, limit, reset_time)
            - is_allowed: 是否允许请求
            - remaining: 剩余请求数
            - limit: 最大请求数
            - reset_time: 窗口重置时间戳（秒）
        """
        current_time = time.time()

        with self._lock:
            # 获取该 IP 的请求记录
            record = self._store.get(client_ip)

            if record is None:
                # 首次请求，创建新记录
                self._store[client_ip] = (1, current_time)
                return True, self.max_requests - 1, self.max_requests, int(current_time + self.window_seconds)

            request_count, window_start = record

            # 检查是否在当前时间窗口内
            if current_time - window_start < self.window_seconds:
                # 在窗口内，检查请求数
                if request_count >= self.max_requests:
                    # 超过限制
                    reset_time = int(window_start + self.window_seconds)
                    return False, 0, self.max_requests, reset_time
                else:
                    # 未超过限制，增加计数
                    self._store[client_ip] = (request_count + 1, window_start)
                    remaining = self.max_requests - request_count - 1
                    return True, remaining, self.max_requests, int(window_start + self.window_seconds)
            else:
                # 窗口已过期，重置计数
                self._store[client_ip] = (1, current_time)
                return True, self.max_requests - 1, self.max_requests, int(current_time + self.window_seconds)

    def _cleanup_expired_records(self):
        """
        清理过期的请求记录

        定期清理可以防止内存无限增长。
        在每次请求时检查并清理过期记录。
        """
        current_time = time.time()

        with self._lock:
            # 找出所有过期的 IP 记录
            expired_ips = [
                ip for ip, (_, window_start) in self._store.items()
                if current_time - window_start >= self.window_seconds
            ]

            # 删除过期记录
            for ip in expired_ips:
                del self._store[ip]

            if expired_ips:
                logger.debug(f"清理了 {len(expired_ips)} 个过期的速率限制记录")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        中间件调度方法

        参数：
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理函数

        返回：
            响应对象
        """
        # 排除特定端点（如健康检查）
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # 获取客户端 IP
        client_ip = self._get_client_ip(request)

        # 定期清理过期记录（每次请求时检查）
        self._cleanup_expired_records()

        # 检查速率限制
        is_allowed, remaining, limit, reset_time = self._check_rate_limit(client_ip)

        # 构建响应头
        rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if not is_allowed:
            # 超过限制，返回 429 错误
            logger.warning(f"IP {client_ip} 超过速率限制: {limit} 请求/{self.window_seconds} 秒")

            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": reset_time - int(time.time()),
                },
                headers={
                    **rate_limit_headers,
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )

        # 允许请求，继续处理
        response = await call_next(request)

        # 添加速率限制响应头
        for key, value in rate_limit_headers.items():
            response.headers[key] = value

        return response

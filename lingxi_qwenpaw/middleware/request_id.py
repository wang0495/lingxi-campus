"""
请求追踪中间件

为每个请求生成唯一 ID，便于日志追踪和问题排查。
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# 使用 ContextVar 存储请求 ID，便于在整个请求生命周期中访问
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """
    获取当前请求的 ID

    Returns:
        当前请求的唯一 ID，如果不在请求上下文中则返回空字符串
    """
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """
    日志过滤器，在日志记录中添加请求 ID

    使用方式：
        在 logger 配置中添加此过滤器，日志格式中可使用 %(request_id)s 占位符
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        为日志记录添加 request_id 属性

        Args:
            record: 日志记录对象

        Returns:
            始终返回 True，允许所有日志通过
        """
        record.request_id = get_request_id()
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求 ID 中间件

    功能：
    1. 为每个请求生成唯一 ID（UUID4）
    2. 如果请求头包含 X-Request-ID，则使用该值
    3. 将请求 ID 存储到 contextvars 中，便于其他模块访问
    4. 在响应头中返回 X-Request-ID
    """

    # 请求头名称
    REQUEST_ID_HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求，添加请求 ID

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            响应对象
        """
        # 1. 获取或生成请求 ID
        request_id = request.headers.get(self.REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # 2. 存储到 contextvars
        token = _request_id_ctx.set(request_id)

        try:
            # 3. 调用下一个处理函数
            response = await call_next(request)

            # 4. 在响应头中返回请求 ID
            response.headers[self.REQUEST_ID_HEADER] = request_id

            return response
        finally:
            # 5. 清理 contextvars，避免内存泄漏
            _request_id_ctx.reset(token)

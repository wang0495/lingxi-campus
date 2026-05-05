"""
灵犀校园自定义异常模块

定义项目中使用的所有自定义异常类，提供统一的错误处理机制。
"""


class LingxiError(Exception):
    """
    灵犀校园异常基类

    所有自定义异常都应继承此类，提供统一的错误码和错误消息管理。

    Attributes:
        error_code: 错误码，用于标识具体的错误类型
        message: 错误消息，描述错误详情
    """

    # 默认错误码
    default_error_code = "LINGXI_ERROR"
    # 默认错误消息
    default_message = "灵犀校园系统错误"

    def __init__(self, message: str = None, error_code: str = None, **kwargs):
        """
        初始化异常

        Args:
            message: 错误消息，如果未提供则使用默认消息
            error_code: 错误码，如果未提供则使用默认错误码
            **kwargs: 额外的上下文信息，将存储在 details 中
        """
        self.error_code = error_code or self.default_error_code
        self.message = message or self.default_message
        self.details = kwargs

        # 构建完整的错误消息
        full_message = f"[{self.error_code}] {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            full_message += f" ({details_str})"

        super().__init__(full_message)

    def to_dict(self) -> dict:
        """
        将异常信息转换为字典格式

        Returns:
            包含错误码、错误消息和详情的字典
        """
        result = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result

    def __str__(self) -> str:
        """返回错误消息字符串"""
        return self.message

    def __repr__(self) -> str:
        """返回异常的详细表示"""
        return f"{self.__class__.__name__}(error_code={self.error_code!r}, message={self.message!r})"


class DatabaseError(LingxiError):
    """
    数据库操作错误

    当数据库操作失败时抛出，包括连接失败、查询错误、事务错误等。

    Examples:
        >>> raise DatabaseError("用户数据保存失败", table="users", operation="insert")
    """

    default_error_code = "DATABASE_ERROR"
    default_message = "数据库操作失败"


class AuthenticationError(LingxiError):
    """
    认证错误

    当用户认证失败时抛出，包括登录失败、令牌过期、权限不足等。

    Examples:
        >>> raise AuthenticationError("用户名或密码错误", username="test")
    """

    default_error_code = "AUTHENTICATION_ERROR"
    default_message = "认证失败"


class ValidationError(LingxiError):
    """
    验证错误

    当数据验证失败时抛出，包括输入格式错误、必填字段缺失、数据范围错误等。

    Examples:
        >>> raise ValidationError("邮箱格式不正确", field="email", value="invalid-email")
    """

    default_error_code = "VALIDATION_ERROR"
    default_message = "数据验证失败"


class APIError(LingxiError):
    """
    外部 API 调用错误

    当调用外部 API 失败时抛出，包括网络错误、API 响应错误、超时等。

    Examples:
        >>> raise APIError("大模型 API 调用失败", api_name="qwen", status_code=500)
    """

    default_error_code = "API_ERROR"
    default_message = "外部 API 调用失败"


class ConfigurationError(LingxiError):
    """
    配置错误

    当系统配置错误时抛出，包括配置文件缺失、配置项无效、环境变量错误等。

    Examples:
        >>> raise ConfigurationError("缺少必要的配置项", config_key="DATABASE_URL")
    """

    default_error_code = "CONFIGURATION_ERROR"
    default_message = "系统配置错误"


class RateLimitError(LingxiError):
    """
    速率限制错误

    当触发速率限制时抛出，包括 API 调用频率超限、请求过于频繁等。

    Attributes:
        retry_after: 建议的重试等待时间（秒）

    Examples:
        >>> raise RateLimitError("API 调用频率超限", retry_after=60)
    """

    default_error_code = "RATE_LIMIT_ERROR"
    default_message = "请求频率超限"

    def __init__(self, message: str = None, error_code: str = None, retry_after: int = None, **kwargs):
        """
        初始化速率限制异常

        Args:
            message: 错误消息
            error_code: 错误码
            retry_after: 建议的重试等待时间（秒）
            **kwargs: 额外的上下文信息
        """
        self.retry_after = retry_after
        if retry_after is not None:
            kwargs["retry_after"] = retry_after
        super().__init__(message, error_code, **kwargs)

    def to_dict(self) -> dict:
        """
        将异常信息转换为字典格式

        Returns:
            包含错误码、错误消息、详情和重试等待时间的字典
        """
        result = super().to_dict()
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        return result


# 异常类型映射表，便于根据错误码查找异常类
EXCEPTION_MAP = {
    "LINGXI_ERROR": LingxiError,
    "DATABASE_ERROR": DatabaseError,
    "AUTHENTICATION_ERROR": AuthenticationError,
    "VALIDATION_ERROR": ValidationError,
    "API_ERROR": APIError,
    "CONFIGURATION_ERROR": ConfigurationError,
    "RATE_LIMIT_ERROR": RateLimitError,
}


def create_exception_from_dict(error_dict: dict) -> LingxiError:
    """
    从字典创建异常实例

    Args:
        error_dict: 包含错误信息的字典，应包含 error_code 和 message 字段

    Returns:
        对应的异常实例

    Examples:
        >>> error_dict = {"error_code": "DATABASE_ERROR", "message": "连接失败"}
        >>> exc = create_exception_from_dict(error_dict)
        >>> isinstance(exc, DatabaseError)
        True
    """
    error_code = error_dict.get("error_code", "LINGXI_ERROR")
    message = error_dict.get("message")
    details = error_dict.get("details", {})
    retry_after = error_dict.get("retry_after")

    # 根据错误码获取异常类
    exception_class = EXCEPTION_MAP.get(error_code, LingxiError)

    # 如果是速率限制错误，特殊处理 retry_after 参数
    if exception_class == RateLimitError and retry_after is not None:
        return exception_class(message=message, error_code=error_code, retry_after=retry_after, **details)

    return exception_class(message=message, error_code=error_code, **details)

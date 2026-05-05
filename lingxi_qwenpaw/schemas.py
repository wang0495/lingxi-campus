"""
灵犀校园统一响应模型

定义 API 统一响应格式，包括成功响应、错误响应和分页响应。
"""
from typing import Generic, TypeVar, Optional, List, Any, Dict
from pydantic import BaseModel, Field


# 泛型类型变量
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一成功响应模型

    用于包装所有成功的 API 响应，提供一致的响应格式。

    Attributes:
        success: 响应状态，成功时为 True
        data: 响应数据，可以是任意类型
        message: 响应消息，可选

    Examples:
        >>> ApiResponse(data={"user_id": "123"}, message="登录成功")
        ApiResponse(success=True, data={'user_id': '123'}, message='登录成功')
    """

    success: bool = Field(default=True, description="响应状态，成功时为 True")
    data: Optional[T] = Field(default=None, description="响应数据")
    message: Optional[str] = Field(default=None, description="响应消息")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "示例数据"},
                "message": "操作成功"
            }
        }


class ErrorResponse(BaseModel):
    """
    统一错误响应模型

    用于包装所有错误的 API 响应，提供一致的错误格式。

    Attributes:
        success: 响应状态，错误时为 False
        error_code: 错误码，用于标识具体的错误类型
        message: 错误消息，描述错误详情
        details: 额外的错误详情，可选

    Examples:
        >>> ErrorResponse(error_code="VALIDATION_ERROR", message="用户名不能为空")
        ErrorResponse(success=False, error_code='VALIDATION_ERROR', message='用户名不能为空', details=None)
    """

    success: bool = Field(default=False, description="响应状态，错误时为 False")
    error_code: str = Field(description="错误码，用于标识具体的错误类型")
    message: str = Field(description="错误消息，描述错误详情")
    details: Optional[Dict[str, Any]] = Field(default=None, description="额外的错误详情")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "message": "用户名不能为空",
                "details": {"field": "username"}
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应模型

    用于包装分页数据的 API 响应，包含分页信息。

    Attributes:
        success: 响应状态，成功时为 True
        items: 当前页的数据列表
        total: 总记录数
        page: 当前页码（从 1 开始）
        page_size: 每页记录数
        total_pages: 总页数，可选
        message: 响应消息，可选

    Examples:
        >>> PaginatedResponse(
        ...     items=[{"id": 1}, {"id": 2}],
        ...     total=100,
        ...     page=1,
        ...     page_size=10
        ... )
        PaginatedResponse(success=True, items=[{'id': 1}, {'id': 2}], total=100, page=1, page_size=10, total_pages=10, message=None)
    """

    success: bool = Field(default=True, description="响应状态，成功时为 True")
    items: List[T] = Field(default_factory=list, description="当前页的数据列表")
    total: int = Field(ge=0, description="总记录数")
    page: int = Field(ge=1, description="当前页码（从 1 开始）")
    page_size: int = Field(ge=1, le=100, description="每页记录数")
    total_pages: Optional[int] = Field(default=None, description="总页数")
    message: Optional[str] = Field(default=None, description="响应消息")

    def __init__(self, **data):
        super().__init__(**data)
        # 自动计算总页数
        if self.total_pages is None and self.page_size > 0:
            self.total_pages = (self.total + self.page_size - 1) // self.page_size

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "items": [{"id": 1, "name": "项目1"}, {"id": 2, "name": "项目2"}],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "message": "获取成功"
            }
        }


# ─── 便捷工厂函数 ────────────────────────────────────────────────

def success_response(data: Any = None, message: str = None) -> dict:
    """
    创建成功响应字典

    Args:
        data: 响应数据
        message: 响应消息

    Returns:
        统一格式的成功响应字典

    Examples:
        >>> success_response({"user_id": "123"}, "登录成功")
        {'success': True, 'data': {'user_id': '123'}, 'message': '登录成功'}
    """
    response = {"success": True}
    if data is not None:
        response["data"] = data
    if message is not None:
        response["message"] = message
    return response


def error_response(error_code: str, message: str, details: Dict[str, Any] = None) -> dict:
    """
    创建错误响应字典

    Args:
        error_code: 错误码
        message: 错误消息
        details: 额外的错误详情

    Returns:
        统一格式的错误响应字典

    Examples:
        >>> error_response("VALIDATION_ERROR", "用户名不能为空", {"field": "username"})
        {'success': False, 'error_code': 'VALIDATION_ERROR', 'message': '用户名不能为空', 'details': {'field': 'username'}}
    """
    response = {
        "success": False,
        "error_code": error_code,
        "message": message,
    }
    if details is not None:
        response["details"] = details
    return response


def paginated_response(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 10,
    message: str = None
) -> dict:
    """
    创建分页响应字典

    Args:
        items: 当前页的数据列表
        total: 总记录数
        page: 当前页码（从 1 开始）
        page_size: 每页记录数
        message: 响应消息

    Returns:
        统一格式的分页响应字典

    Examples:
        >>> paginated_response([{"id": 1}], 100, 1, 10)
        {'success': True, 'items': [{'id': 1}], 'total': 100, 'page': 1, 'page_size': 10, 'total_pages': 10, 'message': None}
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    response = {
        "success": True,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    if message is not None:
        response["message"] = message
    return response

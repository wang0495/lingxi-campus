"""
日志配置模块

提供统一的日志配置和管理功能，支持控制台和文件输出。
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


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
        # 尝试从 contextvars 获取请求 ID
        try:
            from lingxi_qwenpaw.middleware.request_id import get_request_id
            record.request_id = get_request_id() or "-"
        except Exception:
            record.request_id = "-"
        return True


# 日志格式：[时间] [级别] [请求ID] [模块名] 消息
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(request_id)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 默认日志级别
DEFAULT_LOG_LEVEL = "INFO"

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"

# 全局 logger 缓存，避免重复创建
_loggers: dict[str, logging.Logger] = {}

# 标记是否已初始化根日志配置
_initialized = False


def _ensure_log_dir() -> None:
    """确保日志目录存在"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_log_level() -> int:
    """
    从环境变量获取日志级别

    Returns:
        logging 模块的日志级别常量
    """
    level_name = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


def _setup_root_logger() -> None:
    """
    配置根日志记录器

    添加控制台处理器和文件处理器（按日期轮转）
    """
    global _initialized

    if _initialized:
        return

    _ensure_log_dir()

    # 获取日志级别
    log_level = _get_log_level()

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIdFilter())  # 添加请求 ID 过滤器
    root_logger.addHandler(console_handler)

    # 文件处理器（按日期轮转）
    # midnight: 每天午夜轮转
    # backupCount: 保留最近30天的日志文件
    # encoding: UTF-8 编码
    log_file = LOG_DIR / "lingxi.log"
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RequestIdFilter())  # 添加请求 ID 过滤器
    file_handler.suffix = "%Y-%m-%d"  # 轮转文件后缀格式
    root_logger.addHandler(file_handler)

    _initialized = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器实例

    Args:
        name: logger 名称，通常使用 __name__ 传入。
              如果为 None，返回根日志记录器。

    Returns:
        配置好的 Logger 实例

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条日志消息")
        >>> logger.error("这是一条错误消息")
    """
    # 确保根日志配置已初始化
    _setup_root_logger()

    # 如果未指定名称，返回根日志记录器
    if name is None:
        return logging.getLogger()

    # 检查缓存
    if name in _loggers:
        return _loggers[name]

    # 创建新的 logger
    logger = logging.getLogger(name)
    _loggers[name] = logger

    return logger


def set_log_level(level: str) -> None:
    """
    动态设置日志级别

    Args:
        level: 日志级别名称，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if level.upper() not in level_map:
        raise ValueError(f"无效的日志级别: {level}，可选值: {list(level_map.keys())}")

    log_level = level_map[level.upper()]

    # 更新根日志记录器级别
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 更新所有处理器级别
    for handler in root_logger.handlers:
        handler.setLevel(log_level)

    # 更新环境变量
    os.environ["LOG_LEVEL"] = level.upper()


# 模块初始化时自动配置根日志记录器
# 这样在导入模块时就可以直接使用 get_logger()
_setup_root_logger()

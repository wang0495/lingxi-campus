"""灵犀·校园 — 命令行入口"""
import sys
import os

from lingxi_qwenpaw.logger import get_logger

logger = get_logger(__name__)

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    """主入口函数"""
    import uvicorn
    from lingxi_qwenpaw.api import app
    from lingxi_qwenpaw.config import PROJECT_ROOT
    
    # 加载环境变量
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        logger.info(f"加载环境变量: {env_path}")
    
    # 从环境变量获取配置
    port = int(os.environ.get("PORT", 8002))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    
    logger.info(f"启动灵犀·校园服务...")
    logger.info(f"地址: http://0.0.0.0:{port}")
    logger.info(f"文档: http://0.0.0.0:{port}/docs")
    
    uvicorn.run(
        "lingxi_qwenpaw.api:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
    )


if __name__ == "__main__":
    main()

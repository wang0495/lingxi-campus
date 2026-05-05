# 灵犀·校园 Makefile
# 使用方法: make <command>

.PHONY: help install run dev test lint format clean

# 默认目标
help:
	@echo "灵犀·校园 - 可用命令:"
	@echo "  make install    安装依赖"
	@echo "  make run        启动生产服务"
	@echo "  make dev        启动开发服务（热重载）"
	@echo "  make test       运行测试"
	@echo "  make lint       代码检查"
	@echo "  make format     代码格式化"
	@echo "  make clean      清理临时文件"

# 安装依赖
install:
	pip install -r requirements.txt
	pip install -e .

# 启动生产服务
run:
	cd lingxi_qwenpaw && python api.py

# 启动开发服务（热重载）
dev:
	cd lingxi_qwenpaw && uvicorn api:app --reload --host 0.0.0.0 --port 8002

# 运行测试
test:
	pytest tests/ -v

# 代码检查
lint:
	ruff check lingxi_qwenpaw/

# 代码格式化
format:
	ruff format lingxi_qwenpaw/

# 清理临时文件
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

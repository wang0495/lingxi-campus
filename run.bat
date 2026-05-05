@echo off
REM 灵犀·校园 Windows 启动脚本

if "%1"=="" goto help
if "%1"=="install" goto install
if "%1"=="run" goto run
if "%1"=="dev" goto dev
if "%1"=="test" goto test
if "%1"=="lint" goto lint
if "%1"=="format" goto format
if "%1"=="clean" goto clean
goto help

:help
echo 灵犀·校园 - 可用命令:
echo   run.bat install    安装依赖
echo   run.bat run        启动生产服务
echo   run.bat dev        启动开发服务（热重载）
echo   run.bat test       运行测试
echo   run.bat lint       代码检查
echo   run.bat format     代码格式化
echo   run.bat clean      清理临时文件
goto end

:install
pip install -r requirements.txt
pip install -e .
goto end

:run
cd lingxi_qwenpaw
python api.py
goto end

:dev
cd lingxi_qwenpaw
uvicorn api:app --reload --host 0.0.0.0 --port 8002
goto end

:test
pytest tests/ -v
goto end

:lint
ruff check lingxi_qwenpaw/
goto end

:format
ruff format lingxi_qwenpaw/
goto end

:clean
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc 2>nul
goto end

:end

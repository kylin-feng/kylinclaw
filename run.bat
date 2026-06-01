@echo off
chcp 65001 >nul
setlocal

set ROOT=%~dp0
set PYTHON=%ROOT%python\python.exe

if not exist "%PYTHON%" (
    echo [错误] 未找到内嵌 Python，请确认 python\ 文件夹完整。
    pause
    exit /b 1
)

if "%~1"=="" (
    echo KylinClaw — 轻量级 LLM Agent 框架
    echo.
    echo 用法：
    echo   run.bat examples\basic_agent.py
    echo   run.bat examples\multi_agent.py
    echo   run.bat examples\rag_example.py
    echo   run.bat [你的脚本.py]
    echo.
    echo 直接启动交互式 Python：
    echo   run.bat shell
    echo.
    pause
    exit /b 0
)

if /i "%~1"=="shell" (
    "%PYTHON%"
    exit /b
)

"%PYTHON%" "%ROOT%%~1" %2 %3 %4 %5
if errorlevel 1 (
    echo.
    echo [错误] 脚本执行失败，错误码: %errorlevel%
    pause
)

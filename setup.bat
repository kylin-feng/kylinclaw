@echo off
chcp 65001 >nul
setlocal

set ROOT=%~dp0
set PYTHON_DIR=%ROOT%python
set ZIP=%ROOT%python-embed.zip
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip

if exist "%PYTHON_DIR%\python.exe" (
    echo [OK] Python 环境已存在，无需重复安装。
    goto :done
)

echo [1/3] 下载 Python 3.11 嵌入式运行时...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%ZIP%' -UseBasicParsing"
if errorlevel 1 (
    echo [错误] 下载失败，请检查网络连接。
    pause
    exit /b 1
)

echo [2/3] 解压中...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%ZIP%"

echo [3/3] 配置路径...
(
    echo python311.zip
    echo .
    echo ..
    echo.
    echo #import site
) > "%PYTHON_DIR%\python311._pth"

:done
echo.
echo 环境就绪！运行示例：
echo   run.bat examples\basic_agent.py
echo.
pause

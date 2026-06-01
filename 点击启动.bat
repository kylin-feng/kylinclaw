@echo off
chcp 65001 >nul
set ROOT=%~dp0
set PY=%ROOT%python\python.exe

if not exist "%PY%" (
    echo 首次启动，正在下载 Python 运行环境，请稍候...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile '%ROOT%py.zip' -UseBasicParsing"
    powershell -NoProfile -Command "Expand-Archive -Path '%ROOT%py.zip' -DestinationPath '%ROOT%python' -Force"
    del "%ROOT%py.zip"
    (echo python311.zip & echo . & echo .. & echo. & echo #import site) > "%ROOT%python\python311._pth"
    echo 环境就绪。
    echo.
)

"%PY%"

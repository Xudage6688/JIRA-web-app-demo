@echo off
chcp 65001 >nul
echo ====================================
echo 🚀 启动 DevOps 工具集 (本地版)
echo ====================================
echo.

REM 获取脚本所在目录
cd /d "%~dp0"

echo 📁 当前目录: %CD%
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python
    echo 请先安装 Python 3.9 或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python 已安装
python --version
echo.

REM 检查是否存在虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo 🔧 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo ℹ️  未检测到虚拟环境，使用全局 Python 环境
)

REM 检查 Streamlit 是否安装
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ⚠️  Streamlit 未安装
    echo 🔧 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
    echo ✅ 依赖安装完成
    echo.
)

echo.
echo ====================================
echo 🎉 启动应用...
echo ====================================
echo.
echo 💡 提示:
echo   - 应用将在浏览器中自动打开
echo   - 默认地址: http://127.0.0.1:9999
echo   - 按 Ctrl+C 停止应用
echo.
echo 🐳 ArgoCD 工具将直接可用（无网络限制）
echo.

REM 启动 Streamlit 并直接打开 ArgoCD 页面
start "" "http://127.0.0.1:9999/ArgoCD_Images"
python -m streamlit run app.py

pause


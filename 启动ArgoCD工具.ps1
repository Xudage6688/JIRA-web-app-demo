# ====================================
# 🚀 DevOps 工具集 - 本地启动脚本
# ====================================

# 设置控制台输出编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "🚀 启动 DevOps 工具集 (本地版)" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

Write-Host "📁 当前目录: $PWD" -ForegroundColor Yellow
Write-Host ""

# 检查 Python 是否安装
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 错误: 未找到 Python" -ForegroundColor Red
    Write-Host "请先安装 Python 3.9 或更高版本" -ForegroundColor Yellow
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

Write-Host ""

# 检查虚拟环境
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "🔧 激活虚拟环境..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
    Write-Host "✅ 虚拟环境已激活" -ForegroundColor Green
} else {
    Write-Host "ℹ️  未检测到虚拟环境，使用全局 Python 环境" -ForegroundColor Yellow
}

Write-Host ""

# 检查 Streamlit 是否安装
$streamlitInstalled = python -c "import streamlit" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Streamlit 未安装" -ForegroundColor Yellow
    Write-Host "🔧 正在安装依赖..." -ForegroundColor Yellow
    pip install -r requirements.txt
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 依赖安装失败" -ForegroundColor Red
        Read-Host "按回车键退出"
        exit 1
    }
    
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "🎉 启动应用..." -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 提示:" -ForegroundColor Yellow
Write-Host "  - 应用将在浏览器中自动打开"
Write-Host "  - 默认地址: http://localhost:8501"
Write-Host "  - 按 Ctrl+C 停止应用"
Write-Host ""
Write-Host "🐳 ArgoCD 工具将直接可用（无网络限制）" -ForegroundColor Green
Write-Host ""

# 等待 2 秒让用户看到信息
Start-Sleep -Seconds 2

# 启动 Streamlit（会自动打开浏览器）
try {
    # 先打开浏览器到 ArgoCD 页面
    Start-Process "http://localhost:8501/ArgoCD_Images"
    
    # 启动 Streamlit 应用
    streamlit run app.py
} catch {
    Write-Host "❌ 启动失败: $_" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}


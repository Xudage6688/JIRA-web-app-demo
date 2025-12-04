# 🚀 Streamlit Community Cloud 部署指南

## 项目概述

本项目是一个基于 Streamlit 的 DevOps 工具集，采用多页面架构，包含：
- 📊 Jira Affects Project 分析工具
- 🐳 ArgoCD 镜像查询工具

## 什么是Streamlit Community Cloud？

Streamlit Community Cloud是Streamlit官方提供的免费部署平台，专门为Streamlit应用设计，无需信用卡验证。

## ✨ 主要优势

- ✅ **完全免费** - 无需信用卡
- ✅ **专门为Streamlit优化** - 最佳性能
- ✅ **自动HTTPS** - 安全连接
- ✅ **全球CDN** - 快速访问
- ✅ **自动部署** - 连接GitHub自动更新
- ✅ **应用始终在线** - 无休眠

## 🚀 部署步骤

### 1. 访问Streamlit Cloud
- 打开 [share.streamlit.io](https://share.streamlit.io)
- 使用GitHub账户登录

### 2. 授权访问
- 点击 "Authorize Streamlit Community Cloud"
- 选择你的GitHub账户
- 授权访问你的仓库

### 3. 部署应用
- 点击 "New app"
- 配置部署信息：
  - **Repository**: `Daisy-liu822/webtools`
  - **Branch**: `main`
  - **Main file path**: `app.py`  ← 主入口
  - **App URL**: `webtools` ← 自定义子域名
  - **Advanced settings**:
    - **Requirements file**: `requirements.txt`
    - **Python version**: `3.9`

### 4. 点击 "Deploy"
- 等待部署完成（通常2-5分钟）
- 获得公共访问URL

## 🔧 配置说明

### 文件结构
```
jira-web-app/
├── app.py                      # 主应用入口 ⭐
├── pages/                      # 多页面目录
│   ├── 1_Jira_Affects_Project.py
│   └── 2_🐳_ArgoCD_Images.py
├── modules/                    # 功能模块
│   ├── jira_extractor.py
│   └── argocd_client.py
├── config/                     # 配置目录
├── requirements.txt            # 依赖文件
├── .streamlit/
│   └── config.toml            # Streamlit配置
└── README.md                   # 项目说明
```

### 关键配置
- **主文件**: `app.py` (新的 Landing Page)
- **依赖文件**: `requirements.txt`
- **Python版本**: 3.9

## 🌐 部署后

### 访问应用
- 部署完成后的 URL: **https://webtools.streamlit.app**
- 主页会显示两个工具的入口卡片
- 使用侧边栏可以快速切换不同工具
- 建议将 URL 添加到书签方便访问

### 自动更新
- 每次推送到GitHub的main分支
- Streamlit Cloud会自动重新部署
- 无需手动操作

## ⚠️ 注意事项

### 免费计划限制
- 应用数量：无限制
- 带宽：无限制
- 存储：无限制
- 运行时间：无限制

### 最佳实践
- 保持requirements.txt文件精简
- 避免上传大文件（已设置maxUploadSize = 200MB）
- 定期更新依赖包版本

## 🆘 常见问题

### Q: 部署失败怎么办？
A: 检查requirements.txt中的包版本，确保兼容性

### Q: 如何更新应用？
A: 直接推送到GitHub，Streamlit Cloud会自动更新

### Q: 可以自定义域名吗？
A: 免费计划不支持自定义域名，但可以自定义应用名称

## 🎯 下一步

1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 按照上述步骤部署
3. 享受你的JIRA Web应用！

## 📞 支持

如果遇到问题，可以：
- 查看 [Streamlit文档](https://docs.streamlit.io)
- 访问 [Streamlit论坛](https://discuss.streamlit.io)
- 提交 [GitHub Issue](https://github.com/Daisy-liu822/webtools/issues)
- 联系维护者: daisy.liu@qima.com 
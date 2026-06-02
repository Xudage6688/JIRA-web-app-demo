"""
CircleCI 配置加载器
从统一的 config 目录加载 CircleCI 配置
"""
import json
import os
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "circleci_config.json"

def load_config():
    """加载 CircleCI 配置"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 返回默认配置
            return {
                "api_token": "",
                "api_base_url": "https://circleci.com/api/v2",
                "project_slug": "github/your-org/your-repo",
                "branch": "main"
            }
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return {
            "api_token": "",
            "api_base_url": "https://circleci.com/api/v2",
            "project_slug": "github/your-org/your-repo",
            "branch": "main"
        }

def save_config(config):
    """保存 CircleCI 配置"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

# 加载配置
_config = load_config()

# 导出配置变量
CIRCLECI_API_TOKEN = _config.get("api_token", "")
CIRCLECI_API_BASE_URL = _config.get("api_base_url", "https://circleci.com/api/v2")
PROJECT_SLUG = _config.get("project_slug", "github/your-org/your-repo")
BRANCH = _config.get("branch", "main")

def get_project_url():
    """获取项目API端点"""
    return f"{CIRCLECI_API_BASE_URL}/project/{PROJECT_SLUG}/pipeline"

def get_headers():
    """获取API请求头"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Circle-Token": CIRCLECI_API_TOKEN
    }

def get_pipeline_data():
    """获取pipeline触发数据"""
    return {
        "branch": BRANCH
    }

if __name__ == "__main__":
    # 测试配置加载
    print("CircleCI 配置信息:")
    print(f"API Base URL: {CIRCLECI_API_BASE_URL}")
    print(f"Project Slug: {PROJECT_SLUG}")
    print(f"Branch: {BRANCH}")
    print(f"API Token: {'已配置' if CIRCLECI_API_TOKEN else '未配置'}")

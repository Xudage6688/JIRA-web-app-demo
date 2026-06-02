"""
CircleCI 配置加载器
从统一的 config 目录加载 CircleCI 配置
"""
from typing import Dict, Any
import json
import os
from pathlib import Path
from modules.logging_config import config_logger

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "circleci_config.json"

def load_config() -> Dict[str, Any]:
    """加载 CircleCI 配置"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "api_token": "",
                "api_base_url": "https://circleci.com/api/v2",
                "project_slug": "github/your-org/your-repo",
                "branch": "main"
            }
    except Exception as e:
        config_logger.error(f"加载配置文件失败: {e}")
        return {
            "api_token": "",
            "api_base_url": "https://circleci.com/api/v2",
            "project_slug": "github/your-org/your-repo",
            "branch": "main"
        }

def save_config(config: Dict[str, Any]) -> bool:
    """保存 CircleCI 配置"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        config_logger.error(f"保存配置文件失败: {e}")
        return False

# 加载配置
_config = load_config()

# 导出配置变量
CIRCLECI_API_TOKEN = _config.get("api_token", "")
CIRCLECI_API_BASE_URL = _config.get("api_base_url", "https://circleci.com/api/v2")
PROJECT_SLUG = _config.get("project_slug", "github/your-org/your-repo")
BRANCH = _config.get("branch", "main")

def get_project_url() -> str:
    """获取项目API端点"""
    return f"{CIRCLECI_API_BASE_URL}/project/{PROJECT_SLUG}/pipeline"

def get_headers(token: str = None) -> Dict[str, str]:
    """获取API请求头（统一headers构建，避免重复）

    Args:
        token: 可选的API token，如果不提供则使用配置文件中的
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Circle-Token": token if token else CIRCLECI_API_TOKEN
    }

def get_pipeline_data() -> Dict[str, str]:
    """获取pipeline触发数据"""
    return {
        "branch": BRANCH
    }

if __name__ == "__main__":
    config_logger.info("CircleCI 配置信息:")
    config_logger.info(f"API Base URL: {CIRCLECI_API_BASE_URL}")
    config_logger.info(f"Project Slug: {PROJECT_SLUG}")
    config_logger.info(f"Branch: {BRANCH}")
    config_logger.info(f"API Token: {'已配置' if CIRCLECI_API_TOKEN else '未配置'}")

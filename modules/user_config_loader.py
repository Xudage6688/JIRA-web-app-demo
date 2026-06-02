"""
多用户配置加载器
支持从 users_config.json 加载不同用户的配置
"""

import base64
import json
import os
import requests
from typing import Dict, Optional, List
from requests.auth import HTTPBasicAuth

class UserConfigLoader:
    """多用户配置管理器"""
    
    def __init__(self, config_file: str = "config/users_config.json"):
        self.config_file = config_file
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            else:
                print(f"警告: 配置文件不存在 {self.config_file}")
                self._config = {"users": {}, "default_user": None}
        except Exception as e:
            print(f"加载配置失败: {e}")
            self._config = {"users": {}, "default_user": None}
    
    def get_users_list(self) -> List[str]:
        """获取所有用户名列表"""
        return list(self._config.get("users", {}).keys())
    
    def get_default_user(self) -> Optional[str]:
        """获取默认用户"""
        return self._config.get("default_user")
    
    def get_user_config(self, username: str) -> Optional[Dict]:
        """获取指定用户的完整配置"""
        return self._config.get("users", {}).get(username)
    
    def get_jira_config(self, username: str) -> Optional[Dict]:
        """获取指定用户的JIRA配置"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("jira")
        return None
    
    def get_circleci_config(self, username: str) -> Optional[Dict]:
        """获取指定用户的CircleCI配置"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("circleci")
        return None
    
    def get_argocd_config(self, username: str) -> Optional[Dict]:
        """获取指定用户的ArgoCD配置"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("argocd")
        return None

    def get_jenkins_config(self, username: str) -> Optional[Dict]:
        """获取指定用户的Jenkins配置"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("jenkins")
        return None
    
    def get_user_email(self, username: str) -> Optional[str]:
        """获取用户邮箱"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("email")
        return None
    
    def get_user_display_name(self, username: str) -> Optional[str]:
        """获取用户显示名称"""
        user_config = self.get_user_config(username)
        if user_config:
            return user_config.get("display_name", username)
        return username

    def get_cookies_password(self) -> Optional[str]:
        """获取加密 Cookie 的密码"""
        return self._config.get("cookies", {}).get("password")

    def set_cookies_password(self, password: str) -> bool:
        """设置加密 Cookie 的密码并保存到配置文件"""
        try:
            if "cookies" not in self._config:
                self._config["cookies"] = {}
            self._config["cookies"]["password"] = password
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存 cookies 密码失败: {e}")
            return False

def get_user_config_loader() -> UserConfigLoader:
    """每次调用都从磁盘重新读取配置，确保修改文件后立即生效"""
    return UserConfigLoader()

# 便捷函数
def get_users_list() -> List[str]:
    """获取所有用户列表"""
    return get_user_config_loader().get_users_list()

def get_default_user() -> Optional[str]:
    """获取默认用户"""
    return get_user_config_loader().get_default_user()

def get_jira_config(username: str) -> Optional[Dict]:
    """获取JIRA配置"""
    return get_user_config_loader().get_jira_config(username)

def get_circleci_config(username: str) -> Optional[Dict]:
    """获取CircleCI配置"""
    return get_user_config_loader().get_circleci_config(username)

def get_argocd_config(username: str) -> Optional[Dict]:
    """获取ArgoCD配置"""
    return get_user_config_loader().get_argocd_config(username)

def get_jenkins_config(username: str) -> Optional[Dict]:
    """获取Jenkins配置"""
    return get_user_config_loader().get_jenkins_config(username)


def build_jira_auth_headers(email: str, api_token: str) -> Dict[str, str]:
    """构建 Jira Basic Auth 请求头（供所有 Jira 操作统一复用）"""
    auth_str = f"{email}:{api_token}"
    auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
    return {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/json'
    }


def build_jenkins_auth(username: str, api_token: str) -> HTTPBasicAuth:
    """构建 Jenkins HTTPBasicAuth 对象（供所有 Jenkins 操作统一复用）"""
    return HTTPBasicAuth(username, api_token)


def build_circleci_headers(api_token: str) -> Dict[str, str]:
    """构建 CircleCI API 请求头（供所有 CircleCI 操作统一复用）"""
    return {
        'Circle-Token': api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


def parse_api_error_message(
    response: requests.Response,
    max_length: int = 200
) -> str:
    """解析 API 错误响应消息（供所有 API 操作统一复用）

    Args:
        response: requests.Response 对象
        max_length: 返回消息的最大长度

    Returns:
        错误消息字符串
    """
    try:
        error_data = response.json()
        return error_data.get('message', response.text[:max_length])
    except (requests.exceptions.JSONDecodeError, ValueError):
        return response.text[:max_length] if response.text else f"HTTP {response.status_code}"


def sanitize_error_message(error_msg: str) -> str:
    """Remove sensitive information from error messages before displaying to users.

    This function redacts API tokens, passwords, auth headers, and other
    sensitive data that may be leaked in error messages.

    Args:
        error_msg: The original error message that may contain sensitive data.

    Returns:
        Sanitized error message with sensitive data redacted.
    """
    import re

    # Pattern for common API tokens/keys (redacts them)
    patterns = [
        (r'Bearer [a-zA-Z0-9_-]+', 'Bearer ***'),
        (r'token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+', 'api_key=***'),
        (r'password["\']?\s*[:=]\s*["\']?[^\s,}\]]+', 'password=***'),
        (r'Basic [a-zA-Z0-9+/=]+', 'Basic ***'),
        (r'Circle-Token [a-zA-Z0-9_-]+', 'Circle-Token ***'),
        # GitHub PATs
        (r'(ghp|github_pat|gho)_[a-zA-Z0-9_-]+', '[GITHUB_TOKEN]***'),
        # Jira API tokens
        (r'jira[_-]?token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+', 'jira_token=***'),
    ]

    result = error_msg
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result

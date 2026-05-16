"""
GitHub Kustomize 客户端模块
从 GitOps 仓库读取 kustomization.yml 获取镜像信息（示例配置）
"""

import requests
import yaml
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


class GitHubKustomizeClient:
    """GitHub Kustomize 客户端类"""

    # GitHub 仓库配置（示例配置）
    REPO_OWNER = "demo-org"
    REPO_NAME = "demo-apps-descriptors"
    REPO_BRANCH = "main"
    BASE_PATH = "kustomize/overlays"

    # 支持的环境配置
    SUPPORTED_ENVIRONMENTS = {
        'dev': {'path': 'dev', 'display_name': 'Development', 'description': '开发环境'},
        'preprod': {'path': 'preprod', 'display_name': 'PreProd', 'description': '预生产环境'},
        'staging': {'path': 'staging', 'display_name': 'Staging', 'description': '测试环境'},
        'prod': {'path': 'prod', 'display_name': 'Production', 'description': '生产环境'}
    }

    def __init__(self, environment: str, github_token: Optional[str] = None):
        if environment not in self.SUPPORTED_ENVIRONMENTS:
            raise ValueError(f"不支持的环境: {environment}")
        self.environment = environment
        self.env_config = self.SUPPORTED_ENVIRONMENTS[environment]
        self.github_token = github_token
        self.session = requests.Session()
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

    def validate_token(self) -> Tuple[bool, str]:
        if not self.github_token:
            return True, "无Token（公共仓库模式）"
        try:
            url = "https://api.github.com/user"
            response = self.session.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('login', 'Unknown')
                return True, f"Token有效 (用户: {username})"
            return False, "Token无效或已过期"
        except Exception as e:
            return False, f"Token验证异常: {str(e)}"

    def get_raw_file_content(self, file_path: str) -> Optional[str]:
        url = f"https://raw.githubusercontent.com/{self.REPO_OWNER}/{self.REPO_NAME}/{self.REPO_BRANCH}/{file_path}"
        try:
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            raise Exception(f"获取文件失败: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")

    def parse_kustomization_file(self, content: str) -> Dict:
        try:
            return yaml.safe_load(content)
        except Exception as e:
            raise Exception(f"YAML 解析失败: {str(e)}")

    def extract_image_tag(self, kustomization_data: Dict, service_name: str) -> str:
        images = kustomization_data.get('images', [])
        if not images:
            raise Exception("未找到 images 配置")
        for image_config in images:
            if isinstance(image_config, dict):
                name = image_config.get('name', '')
                new_tag = image_config.get('newTag', '')
                if name == service_name or service_name in name:
                    if new_tag:
                        return new_tag
        if len(images) == 1 and isinstance(images[0], dict):
            return images[0].get('newTag', '')
        raise Exception(f"未找到服务 {service_name} 的镜像标签")

    def get_service_image_tag(self, service_name: str) -> str:
        env_path = self.env_config['path']
        file_path = f"{self.BASE_PATH}/{env_path}/{service_name}/kustomization.yml"
        content = self.get_raw_file_content(file_path)
        kustomization_data = self.parse_kustomization_file(content)
        return self.extract_image_tag(kustomization_data, service_name)

    def query_multiple_services(self, service_names: List[str]) -> Dict[str, any]:
        results = {'success': {}, 'failed': {}, 'warnings': [], 'last_updates': {}}

        def fetch_one(svc: str):
            try:
                return svc, self.get_service_image_tag(svc), None
            except Exception as e:
                return svc, None, str(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_one, svc): svc for svc in service_names}
            for future in as_completed(futures):
                svc, tag, err = future.result()
                if err:
                    results['failed'][svc] = err
                else:
                    results['success'][svc] = tag
        return results

    @staticmethod
    def list_environments() -> List[str]:
        return list(GitHubKustomizeClient.SUPPORTED_ENVIRONMENTS.keys())

    @staticmethod
    def get_repo_url() -> str:
        return f"https://github.com/{GitHubKustomizeClient.REPO_OWNER}/{GitHubKustomizeClient.REPO_NAME}"

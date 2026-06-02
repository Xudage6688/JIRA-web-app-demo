"""
ArgoCD API 客户端模块
提供与 ArgoCD API 交互的核心功能（示例配置）
"""

import requests
import yaml
import json
import base64
import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# SSL 验证控制说明：
# - 生产环境：始终启用 SSL 验证
# - 开发环境：设置 APP_ENV=development 且 ARGOCD_SKIP_VERIFY=true 可禁用
# 安全警告：禁用 SSL 验证存在中间人攻击风险，仅用于本地开发测试


class ArgoCDClient:
    """ArgoCD API 客户端类（线程安全，支持资源清理）"""

    # 支持的环境配置（示例配置，实际使用时替换为您的环境）
    SUPPORTED_ENVIRONMENTS = {
        'preprod': {
            'server': 'https://argocd.preprod.example.com',
            'app_prefix': 'preprod-',
            'app_suffix': '--preprod'
        },
        'staging': {
            'server': 'https://argocd.staging.example.com',
            'app_prefix': 'staging-',
            'app_suffix': '--staging'
        },
        'prod': {
            'server': 'https://argocd.prod.example.com',
            'app_prefix': 'prod-',
            'app_suffix': '--prod'
        }
    }

    def __init__(self, environment: str, token: str):
        """
        初始化 ArgoCD 客户端

        Args:
            environment: 环境名称 (preprod/staging/prod)
            token: ArgoCD Bearer Token
        """
        if environment not in self.SUPPORTED_ENVIRONMENTS:
            raise ValueError(f"不支持的环境: {environment}. 支持的环境: {', '.join(self.SUPPORTED_ENVIRONMENTS.keys())}")

        self.environment = environment
        self.env_config = self.SUPPORTED_ENVIRONMENTS[environment]
        self.server_url = self.env_config['server']
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # SSL验证控制：仅在开发模式下允许禁用（安全改进）
        app_env = os.environ.get("APP_ENV", "production")
        skip_verify = os.environ.get("ARGOCD_SKIP_VERIFY", "false").lower() == "true"
        self.verify_ssl = not (app_env == "development" and skip_verify)

        # 创建 Session 实例复用 HTTP 连接
        self.session = requests.Session()
        # 线程锁保护并发 Session 访问
        self._session_lock = threading.Lock()

    def close(self) -> None:
        """关闭 Session 释放连接资源"""
        if self.session:
            self.session.close()
            self.session = None

    def __enter__(self) -> "ArgoCDClient":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """上下文管理器退出，自动清理资源"""
        self.close()
        return False

    def _validate_app_name(self, app_name: str) -> str:
        """验证应用名称格式并进行 URL 编码（防止 SSRF）

        Args:
            app_name: 应用名称

        Returns:
            URL 安全的应用名称

        Raises:
            ValueError: 应用名称格式无效
        """
        if not app_name or len(app_name) > 100:
            raise ValueError(f"应用名称无效或过长: {app_name}")
        # 只允许字母、数字、连字符
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$', app_name):
            raise ValueError(f"应用名称格式无效: {app_name}（只允许字母、数字、连字符）")
        return quote(app_name, safe='')

    def validate_token(self) -> Tuple[bool, str]:
        """验证 Token 有效性和过期时间"""
        try:
            parts = self.token.split('.')
            if len(parts) != 3:
                return False, "Token格式不正确"
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            try:
                decoded_payload = base64.urlsafe_b64decode(payload)
                payload_data = json.loads(decoded_payload)
            except Exception:
                return False, "Token payload解析失败"

            if 'exp' in payload_data:
                exp_timestamp = payload_data['exp']
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                current_datetime = datetime.now()

                if current_datetime > exp_datetime:
                    return False, f"Token已过期 (过期时间: {exp_datetime.strftime('%Y-%m-%d %H:%M:%S')})"
                else:
                    remaining_time = exp_datetime - current_datetime
                    days = remaining_time.days
                    hours, remainder = divmod(remaining_time.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)

                    if days > 0:
                        time_str = f"{days}天{hours}小时"
                    elif hours > 0:
                        time_str = f"{hours}小时{minutes}分钟"
                    else:
                        time_str = f"{minutes}分钟"

                    return True, f"Token有效 (剩余时间: {time_str})"
            else:
                return True, "Token格式正确，但无过期时间信息"

        except Exception as e:
            return False, f"Token验证失败: {str(e)}"

    def get_application(self, app_name: str) -> Optional[Dict]:
        """获取应用信息（线程安全）

        Args:
            app_name: 应用名称

        Returns:
            应用信息字典
        """
        safe_name = self._validate_app_name(app_name)
        url = f"{self.server_url}/api/v1/applications/{safe_name}"
        try:
            with self._session_lock:
                response = self.session.get(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise Exception(f"应用不存在: {app_name}")
            elif response.status_code == 403:
                raise Exception(f"权限被拒绝，请检查 Token 权限")
            elif response.status_code == 401:
                raise Exception(f"Token 无效或已过期")
            else:
                raise Exception(f"获取应用失败: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")

    def get_app_revision(self, app_name: str) -> str:
        """获取应用当前部署的 revision"""
        app_info = self.get_application(app_name)
        if not app_info:
            raise Exception("无法获取应用信息")
        operation_state = app_info.get("status", {}).get("operationState")
        if not operation_state:
            raise Exception("应用未执行过部署")
        revision = operation_state.get("operation", {}).get("sync", {}).get("revision")
        if not revision:
            raise Exception("应用没有有效的 revision")
        return revision

    def get_manifests(self, app_name: str, revision: str) -> List[str]:
        """获取应用的 manifest 清单（线程安全）

        Args:
            app_name: 应用名称
            revision: Git revision

        Returns:
            manifest 列表
        """
        safe_name = self._validate_app_name(app_name)
        url = f"{self.server_url}/api/v1/applications/{safe_name}/manifests"
        try:
            with self._session_lock:
                response = self.session.get(
                    url, headers=self.headers, params={"revision": revision}, verify=self.verify_ssl, timeout=30
                )
            if response.status_code == 200:
                return response.json()["manifests"]
            else:
                raise Exception(f"获取 manifest 失败: {response.status_code}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取 manifest 失败: {str(e)}")

    def extract_images_from_manifests(self, manifests_list: List[str]) -> Dict[str, str]:
        """从 manifest 列表中提取镜像信息"""
        images = {}
        for manifest in manifests_list:
            try:
                y = yaml.safe_load(manifest)
                if not y or "kind" not in y:
                    continue
                spec = y.get("spec", {})
                container_paths = []
                if "template" in spec:
                    container_paths.append(spec["template"].get("spec", {}).get("containers", []))
                elif y.get("kind") == "Pod" and "template" not in y:
                    container_paths.append(spec.get("containers", []))
                elif "containers" in y.get("spec", {}):
                    container_paths.append(spec["containers"])

                for containers in container_paths:
                    for container in containers:
                        name = container.get("name", "-")
                        image = container.get("image", "-")
                        if name != "-" and image != "-":
                            images[name] = image
            except Exception:
                continue
        return images

    def get_service_images(self, service_name: str) -> Dict[str, str]:
        """获取服务的镜像信息"""
        app_name = f"{self.env_config['app_prefix']}{service_name}{self.env_config['app_suffix']}"
        revision = self.get_app_revision(app_name)
        manifests = self.get_manifests(app_name, revision)
        images = self.extract_images_from_manifests(manifests)
        result = {}
        if service_name in images:
            image_url = images[service_name]
            tag = image_url.split(":")[-1] if ":" in image_url else "latest"
            result[service_name] = tag
        elif images:
            first_container = list(images.keys())[0]
            first_image = images[first_container]
            tag = first_image.split(":")[-1] if ":" in first_image else "latest"
            result[service_name] = tag
        return result

    def query_multiple_services(self, service_names: List[str], max_workers: int = 10) -> Dict[str, any]:
        """批量查询多个服务的镜像信息（并发，线程安全）

        注意：并发查询时每个线程使用独立的 HTTP 连接，
        主 Session 仅用于非并发场景的连接复用。

        Args:
            service_names: 服务名称列表
            max_workers: 最大并发数

        Returns:
            {'success': {service: tag}, 'failed': {service: error}}
        """
        results = {'success': {}, 'failed': {}}

        def fetch_one(svc: str) -> Tuple[str, Optional[Dict[str, str]], Optional[str]]:
            # 每个线程独立请求，避免 Session 竞态
            try:
                return svc, self.get_service_images(svc), None
            except Exception as e:
                return svc, None, str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, svc): svc for svc in service_names}
            for future in as_completed(futures):
                svc, images, err = future.result()
                if err:
                    results['failed'][svc] = err
                else:
                    results['success'].update(images)
        return results

    @staticmethod
    def get_environment_config(environment: str) -> Dict:
        """获取环境配置"""
        return ArgoCDClient.SUPPORTED_ENVIRONMENTS.get(environment, {})

    @staticmethod
    def list_environments() -> List[str]:
        """列出所有支持的环境"""
        return list(ArgoCDClient.SUPPORTED_ENVIRONMENTS.keys())

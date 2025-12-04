"""
ArgoCD API 客户端模块
提供与 ArgoCD API 交互的核心功能
"""

import requests
import yaml
import json
import base64
import urllib3
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# 屏蔽证书警告（测试环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ArgoCDClient:
    """ArgoCD API 客户端类"""
    
    # 支持的环境配置
    SUPPORTED_ENVIRONMENTS = {
        'preprod': {
            'server': 'https://argocd.qcore-preprod.qima.com',
            'app_prefix': 'preprod-',
            'app_suffix': '--qcore-preprod'
        },
        'staging': {
            'server': 'https://argocd.qcore-staging.qima.com',
            'app_prefix': 'staging-',
            'app_suffix': '--qcore-staging'
        },
        'prod': {
            'server': 'https://argocd.qcore-prod.qima.com',
            'app_prefix': 'prod-',
            'app_suffix': '--qcore-prod'
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
    
    def validate_token(self) -> Tuple[bool, str]:
        """
        验证 JWT Token 的有效性和过期时间
        
        Returns:
            (is_valid, message): 验证结果和消息
        """
        try:
            # JWT token 由三部分组成，用'.'分隔
            parts = self.token.split('.')
            if len(parts) != 3:
                return False, "Token格式不正确，不是有效的JWT"
            
            # 解析 payload 部分（第二部分）
            payload = parts[1]
            # 添加必要的 padding
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            
            try:
                decoded_payload = base64.urlsafe_b64decode(payload)
                payload_data = json.loads(decoded_payload)
            except Exception:
                return False, "Token payload解析失败"
            
            # 检查过期时间
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
        """
        获取应用信息
        
        Args:
            app_name: 应用名称
            
        Returns:
            应用信息字典，失败返回 None
        """
        url = f"{self.server_url}/api/v1/applications/{app_name}"
        try:
            response = requests.get(url, headers=self.headers, verify=False, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise Exception(f"应用不存在: {app_name}")
            elif response.status_code == 403:
                raise Exception(f"权限被拒绝，请检查 Token 权限")
            elif response.status_code == 401:
                raise Exception(f"Token 无效或已过期")
            else:
                raise Exception(f"获取应用失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"请求失败: {str(e)}")
    
    def get_app_revision(self, app_name: str) -> str:
        """
        获取应用当前部署的 revision
        
        Args:
            app_name: 应用名称
            
        Returns:
            revision 字符串
        """
        app_info = self.get_application(app_name)
        if not app_info:
            raise Exception("无法获取应用信息")
        
        operation_state = app_info.get("status", {}).get("operationState")
        if not operation_state:
            raise Exception("应用未执行过部署，无 operationState")
        
        revision = operation_state.get("operation", {}).get("sync", {}).get("revision")
        if not revision:
            raise Exception("应用没有有效的 revision，请确认是否已同步")
        
        return revision
    
    def get_manifests(self, app_name: str, revision: str) -> List[str]:
        """
        获取应用的 manifest 清单
        
        Args:
            app_name: 应用名称
            revision: Git revision
            
        Returns:
            manifest 列表
        """
        url = f"{self.server_url}/api/v1/applications/{app_name}/manifests"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={"revision": revision},
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()["manifests"]
            else:
                raise Exception(f"获取 manifest 失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取 manifest 失败: {str(e)}")
    
    def extract_images_from_manifests(self, manifests_list: List[str]) -> Dict[str, str]:
        """
        从 manifest 列表中提取镜像信息
        
        Args:
            manifests_list: manifest YAML 字符串列表
            
        Returns:
            {container_name: image_url} 字典
        """
        images = {}
        
        for manifest in manifests_list:
            try:
                y = yaml.safe_load(manifest)
                if not y or "kind" not in y:
                    continue
                
                kind = y["kind"]
                container_paths = []
                
                # 兼容各种顶层结构
                spec = y.get("spec", {})
                if "template" in spec:
                    # Deployment / StatefulSet / DaemonSet
                    container_paths.append(spec["template"].get("spec", {}).get("containers", []))
                elif y.get("kind") == "Pod" and "template" not in y:
                    # Pod
                    container_paths.append(spec.get("containers", []))
                elif kind == "Job" and "jobTemplate" in spec:
                    container_paths.append(spec["jobTemplate"]["spec"]["template"]["spec"]["containers"])
                elif kind == "CronJob" and "cronJobTemplate" in spec:
                    container_paths.append(spec["cronJobTemplate"]["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"])
                elif "containers" in y.get("spec", {}):
                    container_paths.append(spec["containers"])
                
                # 遍历所有 container
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
        """
        获取服务的镜像信息（高级封装）
        
        Args:
            service_name: 服务名称（不含环境前后缀）
            
        Returns:
            {service_name: image_tag} 字典
        """
        # 构建完整应用名
        app_name = f"{self.env_config['app_prefix']}{service_name}{self.env_config['app_suffix']}"
        
        # 获取 revision
        revision = self.get_app_revision(app_name)
        
        # 获取 manifests
        manifests = self.get_manifests(app_name, revision)
        
        # 提取镜像
        images = self.extract_images_from_manifests(manifests)
        
        # 提取主服务镜像（过滤第三方组件）
        result = {}
        
        # 优先选择与服务名匹配的容器
        if service_name in images:
            image_url = images[service_name]
            tag = image_url.split(":")[-1] if ":" in image_url else "latest"
            result[service_name] = tag
        else:
            # 如果没有匹配的，使用第一个非第三方镜像
            for container_name, image_url in images.items():
                if container_name not in ["nginx-prometheus-exporter", "prometheus-exporter"]:
                    tag = image_url.split(":")[-1] if ":" in image_url else "latest"
                    result[service_name] = tag
                    break
        
        # 如果仍然没有找到，返回第一个镜像
        if not result and images:
            first_container = list(images.keys())[0]
            first_image = images[first_container]
            tag = first_image.split(":")[-1] if ":" in first_image else "latest"
            result[service_name] = tag
        
        return result
    
    def query_multiple_services(self, service_names: List[str]) -> Dict[str, any]:
        """
        批量查询多个服务的镜像信息
        
        Args:
            service_names: 服务名称列表
            
        Returns:
            {
                'success': {service_name: image_tag, ...},
                'failed': {service_name: error_message, ...}
            }
        """
        results = {
            'success': {},
            'failed': {}
        }
        
        for service_name in service_names:
            try:
                images = self.get_service_images(service_name)
                results['success'].update(images)
            except Exception as e:
                results['failed'][service_name] = str(e)
        
        return results
    
    @staticmethod
    def get_environment_config(environment: str) -> Dict:
        """
        获取环境配置
        
        Args:
            environment: 环境名称
            
        Returns:
            环境配置字典
        """
        return ArgoCDClient.SUPPORTED_ENVIRONMENTS.get(environment, {})
    
    @staticmethod
    def list_environments() -> List[str]:
        """
        列出所有支持的环境
        
        Returns:
            环境名称列表
        """
        return list(ArgoCDClient.SUPPORTED_ENVIRONMENTS.keys())


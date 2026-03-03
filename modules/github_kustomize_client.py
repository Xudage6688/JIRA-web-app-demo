"""
GitHub Kustomize 客户端模块
从 qcore-apps-descriptors 仓库读取 kustomization.yml 获取镜像信息
"""

import requests
import yaml
import base64
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class GitHubKustomizeClient:
    """GitHub Kustomize 客户端类"""
    
    # GitHub 仓库配置
    REPO_OWNER = "asiainspection"
    REPO_NAME = "qcore-apps-descriptors"
    REPO_BRANCH = "main"
    BASE_PATH = "kustomize/overlays"
    
    # 支持的环境配置
    SUPPORTED_ENVIRONMENTS = {
        'preprod': {
            'path': 'preprod',
            'display_name': 'PreProd',
            'description': '预生产环境'
        },
        'staging': {
            'path': 'staging',
            'display_name': 'Staging',
            'description': '测试环境'
        },
        'prod': {
            'path': 'prod',
            'display_name': 'Production',
            'description': '生产环境'
        }
    }
    
    def __init__(self, environment: str, github_token: Optional[str] = None):
        """
        初始化 GitHub Kustomize 客户端
        
        Args:
            environment: 环境名称 (preprod/staging/prod)
            github_token: GitHub Personal Access Token (可选，用于访问私有仓库或提高速率限制)
        """
        if environment not in self.SUPPORTED_ENVIRONMENTS:
            raise ValueError(f"不支持的环境: {environment}. 支持的环境: {', '.join(self.SUPPORTED_ENVIRONMENTS.keys())}")
        
        self.environment = environment
        self.env_config = self.SUPPORTED_ENVIRONMENTS[environment]
        self.github_token = github_token
        
        # 构建请求头
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
    
    def validate_token(self) -> Tuple[bool, str]:
        """
        验证 GitHub Token 的有效性
        
        Returns:
            (is_valid, message): 验证结果和消息
        """
        if not self.github_token:
            # 无token也可以访问公共仓库，但有速率限制
            return True, "无Token（公共仓库模式，速率限制: 60请求/小时）"
        
        try:
            # 测试API调用
            url = "https://api.github.com/user"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('login', 'Unknown')
                
                # 检查速率限制
                rate_limit = response.headers.get('X-RateLimit-Remaining', 'Unknown')
                rate_reset = response.headers.get('X-RateLimit-Reset', '')
                
                if rate_reset:
                    try:
                        reset_time = datetime.fromtimestamp(int(rate_reset))
                        return True, f"Token有效 (用户: {username}, 剩余请求数: {rate_limit}, 重置时间: {reset_time.strftime('%H:%M:%S')})"
                    except:
                        return True, f"Token有效 (用户: {username})"
                else:
                    return True, f"Token有效 (用户: {username})"
            elif response.status_code == 401:
                return False, "Token无效或已过期"
            elif response.status_code == 403:
                return False, "Token权限不足"
            else:
                return False, f"验证失败: {response.status_code}"
                
        except Exception as e:
            return False, f"Token验证异常: {str(e)}"
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        从 GitHub 获取文件内容
        
        Args:
            file_path: 文件路径（相对于仓库根目录）
            
        Returns:
            文件内容字符串，失败返回 None
        """
        url = f"https://api.github.com/repos/{self.REPO_OWNER}/{self.REPO_NAME}/contents/{file_path}"
        params = {"ref": self.REPO_BRANCH}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # GitHub API 返回 base64 编码的内容
                content_base64 = data.get('content', '')
                if content_base64:
                    content = base64.b64decode(content_base64).decode('utf-8')
                    return content
                else:
                    raise Exception("文件内容为空")
            elif response.status_code == 404:
                raise Exception(f"文件不存在: {file_path}")
            elif response.status_code == 403:
                # 检查是否是速率限制问题
                rate_limit = response.headers.get('X-RateLimit-Remaining', '')
                if rate_limit == '0':
                    reset_time = response.headers.get('X-RateLimit-Reset', '')
                    if reset_time:
                        reset_dt = datetime.fromtimestamp(int(reset_time))
                        raise Exception(f"GitHub API 速率限制已达上限，重置时间: {reset_dt.strftime('%H:%M:%S')}")
                    else:
                        raise Exception("GitHub API 速率限制已达上限")
                else:
                    raise Exception("访问被拒绝，可能需要提供GitHub Token")
            elif response.status_code == 401:
                raise Exception("GitHub Token 无效或已过期")
            else:
                raise Exception(f"获取文件失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")
    
    def get_raw_file_content(self, file_path: str) -> Optional[str]:
        """
        直接从 GitHub Raw URL 获取文件内容（备用方案，不占用API速率限制）
        
        Args:
            file_path: 文件路径（相对于仓库根目录）
            
        Returns:
            文件内容字符串，失败返回 None
        """
        url = f"https://raw.githubusercontent.com/{self.REPO_OWNER}/{self.REPO_NAME}/{self.REPO_BRANCH}/{file_path}"
        
        try:
            # Raw URL 需要token（私有仓库）
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.text
            elif response.status_code == 404:
                # 如果是私有仓库且无token，会返回404
                if not self.github_token:
                    raise Exception(f"仓库可能是私有的，需要提供 GitHub Token 才能访问")
                raise Exception(f"文件不存在: {file_path}")
            elif response.status_code == 401 or response.status_code == 403:
                raise Exception("GitHub Token 无效或权限不足，请检查 Token 权限")
            else:
                raise Exception(f"获取文件失败: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")
    
    def parse_kustomization_file(self, content: str) -> Dict:
        """
        解析 kustomization.yml 文件内容
        
        Args:
            content: YAML 文件内容
            
        Returns:
            解析后的字典
        """
        try:
            data = yaml.safe_load(content)
            return data
        except Exception as e:
            raise Exception(f"YAML 解析失败: {str(e)}")
    
    def extract_image_tag(self, kustomization_data: Dict, service_name: str) -> str:
        """
        从 kustomization.yml 数据中提取镜像标签
        
        Args:
            kustomization_data: kustomization.yml 解析后的字典
            service_name: 服务名称
            
        Returns:
            镜像标签字符串
        """
        images = kustomization_data.get('images', [])
        
        if not images:
            raise Exception("kustomization.yml 中未找到 images 配置")
        
        # 查找匹配的服务镜像
        for image_config in images:
            if isinstance(image_config, dict):
                name = image_config.get('name', '')
                new_tag = image_config.get('newTag', '')
                
                # 匹配服务名（可能是完整名称或部分匹配）
                if name == service_name or service_name in name:
                    if new_tag:
                        return new_tag
                    else:
                        raise Exception(f"服务 {service_name} 的镜像配置中未找到 newTag")
        
        # 如果只有一个镜像配置，直接返回
        if len(images) == 1 and isinstance(images[0], dict):
            new_tag = images[0].get('newTag', '')
            if new_tag:
                return new_tag
        
        raise Exception(f"未在 images 配置中找到服务 {service_name} 的镜像标签")
    
    def get_service_image_tag(self, service_name: str) -> str:
        """
        获取服务的镜像标签
        
        Args:
            service_name: 服务名称（不含环境前后缀）
            
        Returns:
            镜像标签字符串
        """
        # 构建文件路径
        env_path = self.env_config['path']
        file_path = f"{self.BASE_PATH}/{env_path}/{service_name}/kustomization.yml"
        
        # 尝试使用 Raw URL（优先，不占用API速率）
        try:
            content = self.get_raw_file_content(file_path)
        except Exception as e:
            # 如果 Raw URL 失败，尝试使用 API
            try:
                content = self.get_file_content(file_path)
            except Exception as api_error:
                # 两种方式都失败
                raise Exception(f"无法获取文件（Raw URL 和 API 均失败）: {str(e)}")
        
        # 解析 YAML
        kustomization_data = self.parse_kustomization_file(content)
        
        # 提取镜像标签
        image_tag = self.extract_image_tag(kustomization_data, service_name)
        
        return image_tag
    
    def get_service_images(self, service_name: str) -> Dict[str, str]:
        """
        获取服务的镜像信息（兼容旧接口）
        
        Args:
            service_name: 服务名称（不含环境前后缀）
            
        Returns:
            {service_name: image_tag} 字典
        """
        image_tag = self.get_service_image_tag(service_name)
        return {service_name: image_tag}
    
    def check_service_exists(self, service_name: str) -> Tuple[bool, str]:
        """
        检查服务在 qcore-apps-descriptors 中是否存在
        
        Args:
            service_name: 服务名称
            
        Returns:
            (exists, message): 是否存在和消息
        """
        env_path = self.env_config['path']
        file_path = f"{self.BASE_PATH}/{env_path}/{service_name}/kustomization.yml"
        
        try:
            # 只检查文件是否存在，不获取内容（使用HEAD请求更快）
            url = f"https://api.github.com/repos/{self.REPO_OWNER}/{self.REPO_NAME}/contents/{file_path}"
            params = {"ref": self.REPO_BRANCH}
            
            response = requests.head(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return True, f"服务 {service_name} 存在于仓库中"
            elif response.status_code == 404:
                return False, f"服务 {service_name} 不存在于仓库中"
            else:
                return False, f"检查失败: {response.status_code}"
                
        except Exception as e:
            return False, f"检查异常: {str(e)}"
    
    def query_multiple_services(self, service_names: List[str]) -> Dict[str, any]:
        """
        批量查询多个服务的镜像信息
        
        Args:
            service_names: 服务名称列表
            
        Returns:
            {
                'success': {service_name: image_tag, ...},
                'failed': {service_name: error_message, ...},
                'warnings': [warning_message, ...]  # 服务名称不一致的警告
            }
        """
        results = {
            'success': {},
            'failed': {},
            'warnings': []
        }
        
        for service_name in service_names:
            try:
                images = self.get_service_images(service_name)
                results['success'].update(images)
            except Exception as e:
                error_msg = str(e)
                results['failed'][service_name] = error_msg
                
                # 如果是文件不存在错误，添加警告
                if "文件不存在" in error_msg or "404" in error_msg:
                    results['warnings'].append(
                        f"⚠️ 服务 '{service_name}' 在 {self.env_config['display_name']} 环境的 qcore-apps-descriptors 仓库中不存在，请检查服务名称是否正确"
                    )
        
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
        return GitHubKustomizeClient.SUPPORTED_ENVIRONMENTS.get(environment, {})
    
    @staticmethod
    def list_environments() -> List[str]:
        """
        列出所有支持的环境
        
        Returns:
            环境名称列表
        """
        return list(GitHubKustomizeClient.SUPPORTED_ENVIRONMENTS.keys())
    
    @staticmethod
    def get_repo_url() -> str:
        """
        获取仓库 URL
        
        Returns:
            GitHub 仓库 URL
        """
        return f"https://github.com/{GitHubKustomizeClient.REPO_OWNER}/{GitHubKustomizeClient.REPO_NAME}"

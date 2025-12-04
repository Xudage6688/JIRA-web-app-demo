# jira_extractor.py
import requests
import json
import csv
import os
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JiraExtractor:
    def __init__(self, base_url: str, api_token: str, email: str):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.email = email
        self.session = requests.Session()
        
        # 设置认证头
        if email:
            # 基本认证（邮箱 + API 令牌）
            self.session.auth = (email, api_token)
        else:
            # Bearer 令牌认证
            self.session.headers.update({
                'Authorization': f'Bearer {api_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
        
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # 加载项目映射配置
        self.project_mappings = self._load_project_mappings()

    def _load_project_mappings(self) -> Dict[str, List[str]]:
        """加载项目映射配置"""
        try:
            mapping_file = "project_mapping.json"
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('project_mappings', {})
            else:
                logger.warning(f"项目映射文件 {mapping_file} 不存在，使用默认映射")
                return {
                    "aca": ["aca-cn"],
                    "public-api": ["public-api-job"]
                }
        except Exception as e:
            logger.error(f"加载项目映射失败: {e}")
            return {}

    def _apply_project_mappings(self, projects: List[str]) -> List[str]:
        """应用项目映射，添加关联项目"""
        if not self.project_mappings:
            return projects
        
        expanded_projects = projects.copy()
        
        for project in projects:
            project_clean = project.strip()
            
            # 检查是否有精确映射规则（避免子字符串误匹配）
            for source_project, target_projects in self.project_mappings.items():
                # 精确匹配（大小写不敏感）
                if source_project.lower() == project_clean.lower():
                    # 添加关联项目
                    for target_project in target_projects:
                        if target_project not in expanded_projects:
                            expanded_projects.append(target_project)
                            logger.info(f"添加关联项目: {source_project} -> {target_project}")
        
        return expanded_projects

    def get_affects_project_field_id(self, known_field_id: str = "customfield_12605") -> str:
        """
        获取 'Affects Project' 字段的 ID
        
        Args:
            known_field_id: 已知的字段 ID（如 customfield_12605）
            
        Returns:
            字段 ID
        """
        logger.info(f"使用已知字段 ID: {known_field_id}")
        return known_field_id

    def search_issues_by_jql(self, jql: str, custom_field_id: str = None, max_results: int = 100) -> List[Dict]:
        """
        使用新的增强 JQL API 搜索问题
        
        Args:
            jql: JQL 查询字符串
            custom_field_id: 'Affects Project' 字段 ID
            max_results: 最大结果数
            
        Returns:
            问题列表
        """
        # 使用新的增强搜索 API
        url = f"{self.base_url}/rest/api/3/search/jql"
        
        # 构建查询参数
        fields = ["summary", "key", "status"]
        if custom_field_id:
            fields.append(custom_field_id)
        
        # 使用 POST 请求发送 JQL 查询
        payload = {
            'jql': jql,
            'fields': fields,
            'maxResults': max_results
        }
        
        try:
            logger.info(f"尝试使用增强 JQL 搜索 API...")
            logger.info(f"URL: {url}")
            logger.info(f"JQL: {jql}")
            
            response = self.session.post(url, json=payload)
            
            if response.status_code == 410:
                logger.warning(f"增强 JQL API 返回 410 Gone，尝试传统 API...")
                # 如果新 API 也不可用，尝试旧的 API
                return self._search_issues_legacy(jql, custom_field_id, max_results)
            
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            total = data.get('total', 0)
            
            logger.info(f"✓ 成功使用增强 JQL API 获取 {len(issues)} 个问题，总计 {total} 个")
            return issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"增强 JQL API 失败: {e}")
            # 尝试使用传统 API
            try:
                return self._search_issues_legacy(jql, custom_field_id, max_results)
            except Exception as e2:
                logger.error(f"所有搜索 API 都失败了: {e2}")
                raise e2

    def _search_issues_legacy(self, jql: str, custom_field_id: str = None, max_results: int = 100) -> List[Dict]:
        """
        使用传统搜索 API（作为备用）
        
        Args:
            jql: JQL 查询字符串
            custom_field_id: 'Affects Project' 字段 ID
            max_results: 最大结果数
            
        Returns:
            问题列表
        """
        # 尝试不同的 API 版本
        api_versions = ["2", "3"]
        last_error = None
        
        for api_version in api_versions:
            try:
                url = f"{self.base_url}/rest/api/{api_version}/search"
                
                # 构建查询参数
                fields = ["summary", "key", "status"]
                if custom_field_id:
                    fields.append(custom_field_id)
                
                params = {
                    'jql': jql,
                    'fields': ','.join(fields),
                    'maxResults': max_results,
                    'startAt': 0
                }
                
                logger.info(f"尝试传统 API v{api_version}...")
                response = self.session.get(url, params=params)
                
                if response.status_code == 410:
                    logger.warning(f"传统 API v{api_version} 返回 410 Gone")
                    last_error = requests.exceptions.HTTPError(f"API v{api_version} 不再可用")
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                issues = data.get('issues', [])
                total = data.get('total', 0)
                
                logger.info(f"✓ 成功使用传统 API v{api_version} 获取 {len(issues)} 个问题，总计 {total} 个")
                return issues
                
            except requests.exceptions.RequestException as e:
                logger.error(f"传统 API v{api_version} 失败: {e}")
                last_error = e
                continue
        
        # 如果所有 API 版本都失败了
        logger.error(f"所有搜索 API 版本都失败了: {last_error}")
        raise last_error

    def search_issues(self, filter_id: str = "24058", custom_field_id: str = None, max_results: int = 100) -> List[Dict]:
        """
        使用过滤器搜索问题
        
        Args:
            filter_id: Jira 过滤器 ID
            custom_field_id: 'Affects Project' 字段 ID
            max_results: 最大结果数
            
        Returns:
            问题列表
        """
        url = f"{self.base_url}/rest/api/3/search"
        
        # 构建查询参数
        fields = ["summary", "key", "status"]
        if custom_field_id:
            fields.append(custom_field_id)
        
        params = {
            'jql': f'filter={filter_id}',
            'fields': ','.join(fields),
            'maxResults': max_results,
            'startAt': 0
        }
        
        try:
            response = self.session.get(url, params=params)
            
            # 如果过滤器 API 返回 410，尝试使用直接 JQL 查询
            if response.status_code == 410:
                logger.warning(f"过滤器 API 返回 410 Gone，尝试直接 JQL 查询...")
                logger.info(f"过滤器 {filter_id} API 已弃用，使用直接 JQL 查询作为备用...")
                
                # 使用精确的 JQL 查询（获取等待发布的已完成问题）
                fallback_jql = (
                    'project = SP '
                    'AND issuetype IN (standardIssueTypes(), subTaskIssueTypes()) '
                    'AND status = Done '
                    'AND resolution = "Waiting to Release" '
                    'AND updated >= -100d '
                    'AND "sp team[dropdown]" != Titan '
                    'ORDER BY Key ASC'
                )
                logger.info(f"备用 JQL: {fallback_jql}")
                return self.search_issues_by_jql(fallback_jql, custom_field_id, max_results)
            
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            total = data.get('total', 0)
            
            logger.info(f"成功获取 {len(issues)} 个问题，总计 {total} 个")
            return issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"搜索问题失败: {e}")
            raise

    def parse_adf_content(self, adf_data: Dict) -> str:
        """
        解析 Atlassian Document Format (ADF) 内容提取文本
        
        Args:
            adf_data: ADF 格式的数据
            
        Returns:
            提取的文本内容
        """
        if not isinstance(adf_data, dict):
            return str(adf_data)
        
        text_parts = []
        
        def extract_text_from_content(content):
            """递归提取内容中的文本"""
            if isinstance(content, list):
                for item in content:
                    extract_text_from_content(item)
            elif isinstance(content, dict):
                if content.get('type') == 'text':
                    text = content.get('text', '')
                    if text and text.strip():
                        text_parts.append(text.strip())
                elif 'content' in content:
                    extract_text_from_content(content['content'])
        
        # 开始提取文本
        if 'content' in adf_data:
            extract_text_from_content(adf_data['content'])
        
        return ' '.join(text_parts)

    def extract_projects_from_text(self, text: str) -> List[str]:
        """
        从文本中提取项目名称（完全按照 API 返回的内容，不做过滤）
        
        Args:
            text: 包含项目信息的文本
            
        Returns:
            项目名称列表
        """
        if not text or text.strip().upper() in ['NONE', 'NA', '']:
            return []
        
        # 移除常见的非项目名称标记
        clean_text = text.strip()
        
        # 移除 +数字 格式（如 "+7"）
        clean_text = re.sub(r'\s*\+\d+', '', clean_text)
        
        # 按空格、逗号、分号、换行符分割
        items = re.split(r'[,;\n\s]+', clean_text)
        
        projects = []
        for item in items:
            item = item.strip()
            
            # 跳过空字符串和太短的字符串
            if not item or len(item) < 2:
                continue
            
            # 跳过明确的非项目名称（只排除明显的无效值）
            if item.upper() in ['NA', 'NONE', 'NULL', '']:
                continue
            
            # 跳过 URL 和路径
            if any(exclude in item.lower() for exclude in ['http', '://', '.com', '.git', '.org']):
                continue
            
            # 添加到项目列表（保持原始大小写）
            projects.append(item)
        
        return projects

    def find_affects_project_field_id(self, filter_id: str) -> Optional[str]:
        """查找Affects Project字段ID（保持向后兼容）"""
        try:
            # 首先尝试使用新的JQL API
            try:
                jql = f'filter={filter_id}'
                issues = self.search_issues_by_jql(jql, max_results=10)
            except Exception as e:
                logger.warning(f"新JQL API失败，尝试传统API: {e}")
                # 如果新API失败，尝试传统API
                url = f"{self.base_url}/rest/api/3/search"
                params = {
                    'jql': f'filter={filter_id}',
                    'fields': 'summary,key',
                    'maxResults': 10,
                    'startAt': 0
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                issues = response.json().get('issues', [])
            
            if not issues:
                logger.warning("过滤器中没有找到问题，使用已知字段ID作为备用")
                return "customfield_12605"
            
            potential_fields = []

            for issue in issues:
                issue_key = issue.get('key', '')
                issue_url = f"{self.base_url}/rest/api/3/issue/{issue_key}?expand=names"
                issue_data = self.session.get(issue_url).json()
                fields = issue_data.get('fields', {})
                names = issue_data.get('names', {})

                for field_id, value in fields.items():
                    if field_id.startswith('customfield_') and value:
                        field_name = names.get(field_id, 'N/A')
                        if any(kw in field_name.lower() or (isinstance(value, str) and kw in value.lower())
                               for kw in ['service', 'cloud', 'legacy', 'web', 'api', 'project']):
                            logger.info(f"找到匹配字段: {field_id} ({field_name})")
                            return field_id

        except Exception as e:
            logger.error(f"字段识别失败: {e}")
            # 如果自动检测失败，返回已知的字段ID作为备用
            logger.info("使用已知字段ID作为备用: customfield_12605")
            return "customfield_12605"
        
        # 如果没有找到匹配的字段，返回已知的字段ID
        logger.info("未找到匹配字段，使用已知字段ID: customfield_12605")
        return "customfield_12605"

    def extract_projects_from_filter(self, filter_id, custom_field_id: str = None) -> List[Dict]:
        """从过滤器提取项目（保持向后兼容）"""
        return self.get_affects_projects(filter_id, custom_field_id)

    def get_affects_projects(self, filter_id, custom_field_id: Optional[str]) -> List[Dict]:
        """获取影响项目列表（使用新的API）"""
        try:
            # 首先尝试使用过滤器搜索
            issues = self.search_issues(filter_id, custom_field_id, max_results=1000)
        except Exception as e:
            logger.error(f"使用过滤器搜索失败: {e}")
            # 如果失败，尝试使用直接JQL查询
            fallback_jql = (
                'project = SP '
                'AND issuetype IN (standardIssueTypes(), subTaskIssueTypes()) '
                'AND status = Done '
                'AND resolution = "Waiting to Release" '
                'AND updated >= -100d '
                'AND "sp team[dropdown]" != Titan '
                'ORDER BY Key ASC'
            )
            issues = self.search_issues_by_jql(fallback_jql, custom_field_id, max_results=1000)
        
        return self._extract_affects_projects(issues, custom_field_id)

    def _extract_affects_projects(self, issues: List[Dict], custom_field_id: Optional[str]) -> List[Dict]:
        """从问题列表中提取 'Affects Project' 信息"""
        results = []
        all_projects = set()
        
        for issue in issues:
            fields = issue.get('fields', {})
            issue_key = issue.get('key', '')
            summary = fields.get('summary', '')
            status = fields.get('status', {}).get('name', '')
            
            # 如果没有字段ID，跳过 Affects Project 提取
            if custom_field_id is None:
                affects_project_raw = ''
            else:
                affects_project_raw = fields.get(custom_field_id, '')
            
            # 处理不同类型的字段值
            projects = []
            affects_project_str = ""
            
            if affects_project_raw:
                if isinstance(affects_project_raw, str):
                    # 字符串类型，直接处理
                    affects_project_str = affects_project_raw
                    projects = self.extract_projects_from_text(affects_project_str)
                elif isinstance(affects_project_raw, list):
                    # 数组类型，提取每个元素的值
                    project_texts = []
                    for item in affects_project_raw:
                        if isinstance(item, dict):
                            # 检查是否是 ADF 格式
                            if 'type' in item and 'content' in item:
                                text = self.parse_adf_content(item)
                                project_texts.append(text)
                            else:
                                # 普通对象，尝试提取 value 或 name 字段
                                value = item.get('value', item.get('name', str(item)))
                                project_texts.append(str(value))
                        else:
                            project_texts.append(str(item))
                    
                    affects_project_str = " ".join(project_texts)
                    projects = self.extract_projects_from_text(affects_project_str)
                elif isinstance(affects_project_raw, dict):
                    # 对象类型，检查是否是 ADF 格式
                    if 'type' in affects_project_raw and 'content' in affects_project_raw:
                        # ADF 格式，解析文本内容
                        affects_project_str = self.parse_adf_content(affects_project_raw)
                        projects = self.extract_projects_from_text(affects_project_str)
                    else:
                        # 普通对象，尝试提取值
                        value = affects_project_raw.get('value', affects_project_raw.get('name', str(affects_project_raw)))
                        affects_project_str = str(value)
                        projects = self.extract_projects_from_text(affects_project_str)
                else:
                    # 其他类型，转换为字符串
                    affects_project_str = str(affects_project_raw)
                    projects = self.extract_projects_from_text(affects_project_str)
                
                # 应用项目映射
                if projects:
                    projects = self._apply_project_mappings(projects)
                    # 重新生成字符串表示
                    affects_project_str = ", ".join(projects)
                
                # 添加项目到总列表
                all_projects.update(projects)
            
            results.append({
                'issue_key': issue_key,
                'summary': summary,
                'status': status,
                'affects_projects': projects,
                'affects_projects_raw': affects_project_str
            })
        
        logger.info(f"发现 {len(all_projects)} 个唯一项目")
        if all_projects:
            logger.info(f"项目: {sorted(all_projects)}")
        
        return results

    def _process_field_value(self, field_val):
        """处理字段值（保持向后兼容）"""
        if isinstance(field_val, str):
            val = field_val.strip()
            return val, [p.strip() for p in val.split(",") if p.strip() and p.strip().upper() != "NA"]
        elif isinstance(field_val, list):
            val = ", ".join([str(i.get('value') if isinstance(i, dict) else i) for i in field_val])
            return val, [str(i.get('value') if isinstance(i, dict) else i).strip() for i in field_val]
        elif isinstance(field_val, dict):
            val = str(field_val.get('value', field_val.get('name', '')))
            return val, [val.strip()]
        else:
            return "", []

    def save_results_to_file(self, results: List[Dict]):
        """保存结果到文件"""
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)

        prefix = f"jira_affects_projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        json_path = os.path.join(results_dir, f"{prefix}.json")
        csv_path = os.path.join(results_dir, f"{prefix}.csv")
        
        # 保存JSON文件
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 准备CSV数据，确保列名匹配
        csv_data = []
        for result in results:
            csv_row = {
                'issue_key': result.get('issue_key', ''),
                'summary': result.get('summary', ''),
                'status': result.get('status', ''),
                'affects_projects_raw': result.get('affects_projects_raw', ''),
                'affects_projects_count': len(result.get('affects_projects', []))
            }
            csv_data.append(csv_row)
        
        # 保存CSV文件
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            if csv_data:
                fieldnames = list(csv_data[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
        
        return json_path, csv_path

    def get_project_mappings(self) -> Dict[str, List[str]]:
        """获取当前项目映射配置"""
        return self.project_mappings.copy()

    def update_project_mappings(self, new_mappings: Dict[str, List[str]]) -> bool:
        """更新项目映射配置"""
        try:
            config = {
                "project_mappings": new_mappings,
                "description": "当检测到左侧项目时，自动添加右侧的关联项目到结果中。支持大小写变体和不同命名格式。",
                "version": "1.1.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d")
            }
            
            with open("project_mapping.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 更新内存中的配置
            self.project_mappings = new_mappings
            return True
        except Exception as e:
            logger.error(f"更新项目映射失败: {e}")
            return False
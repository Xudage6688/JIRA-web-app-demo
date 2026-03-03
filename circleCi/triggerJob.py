import requests
import json
import argparse
import sys
from circleCi.config_loader import get_project_url, get_headers, get_pipeline_data, PROJECT_SLUG, BRANCH

# 安全的打印函数，避免在Streamlit环境中出现I/O错误
def safe_print(msg):
    """安全地打印消息，避免stderr关闭问题"""
    try:
        print(msg)
    except:
        pass  # 静默忽略打印错误

def trigger_circleci_pipeline(project_slug=None, branch=None, api_token=None):
    """
    触发CircleCI pipeline
    
    Args:
        project_slug (str): 项目slug，格式为 vcs-type/org-name/repo-name
        branch (str): 分支名称
        api_token (str): CircleCI API Token（如果不提供则使用配置文件中的）
    """
    # 使用传入的参数或配置文件中的默认值
    current_project_slug = project_slug or PROJECT_SLUG
    current_branch = branch or BRANCH
    
    # 构建API URL
    url = f"https://circleci.com/api/v2/project/{current_project_slug}/pipeline"
    
    # 使用传入的token或配置文件中的token
    if api_token:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Circle-Token": api_token
        }
    else:
        headers = get_headers()
    
    # 构建请求数据
    data = {
        "branch": current_branch
    }
    
    try:
        safe_print(f"正在触发CircleCI pipeline...")
        safe_print(f"项目: {current_project_slug}")
        safe_print(f"分支: {current_branch}")
        safe_print(f"API端点: {url}")
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        safe_print(f"状态码: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            pipeline_id = result.get('id', 'N/A')
            pipeline_number = result.get('number', 'N/A')
            safe_print("✅ Pipeline触发成功!")
            safe_print(f"Pipeline ID: {pipeline_id}")
            safe_print(f"Pipeline Number: {pipeline_number}")
            # 返回pipeline信息字典，便于后续监控
            return {
                'success': True,
                'pipeline_id': pipeline_id,
                'pipeline_number': pipeline_number,
                'status_code': response.status_code
            }
        elif response.status_code == 404:
            safe_print("❌ 404错误 - 项目未找到")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': '项目未找到或无权访问'
            }
        elif response.status_code == 401:
            safe_print("❌ 401错误 - 认证失败")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': 'API Token认证失败'
            }
        elif response.status_code == 403:
            safe_print("❌ 403错误 - 权限不足")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': 'API Token权限不足'
            }
        else:
            safe_print(f"❌ 请求失败，状态码: {response.status_code}")
            safe_print(f"响应内容: {response.text}")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': f'请求失败: {response.text}'
            }
            
    except requests.exceptions.Timeout as e:
        safe_print(f"❌ 请求超时: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': '请求超时，请检查网络连接'
        }
    except requests.exceptions.RequestException as e:
        safe_print(f"❌ 网络请求错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': f'网络请求错误: {str(e)}'
        }
    except json.JSONDecodeError as e:
        safe_print(f"❌ JSON解析错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': 'JSON解析错误'
        }
    except Exception as e:
        safe_print(f"❌ 未知错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': f'未知错误: {str(e)}'
        }

def validate_project_slug(project_slug):
    """
    验证项目slug格式
    
    Args:
        project_slug (str): 项目slug
    
    Returns:
        bool: 验证是否通过
    """
    safe_print("🔍 验证项目配置...")
    safe_print(f"当前项目slug: {project_slug}")
    
    # 检查slug格式
    if '/' not in project_slug or project_slug.count('/') != 2:
        safe_print("❌ 项目slug格式错误")
        safe_print("正确格式应该是: vcs-type/org-name/repo-name")
        safe_print("例如: github/your-org/your-repo")
        return False
    
    vcs_type, org_name, repo_name = project_slug.split('/')
    safe_print(f"VCS类型: {vcs_type}")
    safe_print(f"组织名: {org_name}")
    safe_print(f"仓库名: {repo_name}")
    
    if vcs_type not in ['github', 'bitbucket']:
        safe_print("❌ 不支持的VCS类型，只支持github和bitbucket")
        return False
    
    return True

def setup_argument_parser():
    """
    设置命令行参数解析器
    
    Returns:
        argparse.ArgumentParser: 参数解析器
    """
    parser = argparse.ArgumentParser(
        description="CircleCI Pipeline触发器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python triggerJob.py                                    # 使用配置文件中的默认值
  python triggerJob.py -p github/org/repo                # 指定项目
  python triggerJob.py -p github/org/repo -b develop     # 指定项目和分支
  python triggerJob.py --project github/org/repo --branch feature/new-feature
        """
    )
    
    parser.add_argument(
        '-p', '--project',
        type=str,
        help='项目slug (格式: vcs-type/org-name/repo-name)'
    )
    
    parser.add_argument(
        '-b', '--branch',
        type=str,
        help='分支名称'
    )
    
    parser.add_argument(
        '--list-config',
        action='store_true',
        help='显示当前配置信息'
    )
    
    return parser

def show_current_config():
    """
    显示当前配置信息
    """
    safe_print("📋 当前配置信息:")
    safe_print("=" * 50)
    safe_print(f"项目Slug: {PROJECT_SLUG}")
    safe_print(f"分支名称: {BRANCH}")
    safe_print(f"API Token: {get_headers()['Circle-Token'][:20]}...")
    safe_print("=" * 50)

def main():
    """
    主函数
    """
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    safe_print("🚀 CircleCI Pipeline触发器")
    safe_print("=" * 50)
    
    # 如果只是查看配置，显示后退出
    if args.list_config:
        show_current_config()
        return
    
    # 确定要使用的项目slug和分支
    project_slug = args.project or PROJECT_SLUG
    branch = args.branch or BRANCH
    
    # 显示将要使用的配置
    if args.project or args.branch:
        safe_print("📝 使用参数:")
        if args.project:
            safe_print(f"  项目: {project_slug} (命令行指定)")
        else:
            safe_print(f"  项目: {project_slug} (配置文件默认值)")
        
        if args.branch:
            safe_print(f"  分支: {branch} (命令行指定)")
        else:
            safe_print(f"  分支: {branch} (配置文件默认值)")
        safe_print("")
    
    # 验证项目配置
    if not validate_project_slug(project_slug):
        safe_print("\n💡 解决方案:")
        safe_print("1. 使用 -p 参数指定正确的项目slug")
        safe_print("2. 修改config.py中的PROJECT_SLUG")
        safe_print("3. 检查项目是否存在于CircleCI中")
        sys.exit(1)
    
    safe_print("")
    
    # 触发pipeline
    result = trigger_circleci_pipeline(project_slug, branch)
    
    # 兼容旧版本返回值（True/False）
    if isinstance(result, bool):
        success = result
    else:
        success = result.get('success', False)
    
    if not success:
        safe_print("\n💡 故障排除建议:")
        safe_print("1. 检查项目slug格式是否正确")
        safe_print("2. 验证API token是否有效")
        safe_print("3. 确认项目在CircleCI中已配置")
        safe_print("4. 检查API token权限")
        safe_print("5. 使用 --list-config 查看当前配置")

if __name__ == "__main__":
    main()

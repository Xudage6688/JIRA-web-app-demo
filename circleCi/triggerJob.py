from typing import Dict, Any, Optional
import requests
import json
import argparse
import sys
from circleCi.config_loader import get_project_url, get_headers, get_pipeline_data, PROJECT_SLUG, BRANCH
from modules.logging_config import circleci_logger

def trigger_circleci_pipeline(project_slug: Optional[str] = None, branch: Optional[str] = None, api_token: Optional[str] = None) -> Dict[str, Any]:
    """
    触发CircleCI pipeline

    Args:
        project_slug (str): 项目slug，格式为 vcs-type/org-name/repo-name
        branch (str): 分支名称
        api_token (str): CircleCI API Token（如果不提供则使用配置文件中的）
    """
    current_project_slug = project_slug or PROJECT_SLUG
    current_branch = branch or BRANCH

    url = f"https://circleci.com/api/v2/project/{current_project_slug}/pipeline"
    headers = get_headers(api_token)

    data = {
        "branch": current_branch
    }

    try:
        circleci_logger.info(f"正在触发CircleCI pipeline...")
        circleci_logger.info(f"项目: {current_project_slug}")
        circleci_logger.info(f"分支: {current_branch}")
        circleci_logger.debug(f"API端点: {url}")

        response = requests.post(url, json=data, headers=headers, timeout=30)

        circleci_logger.info(f"状态码: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            pipeline_id = result.get('id', 'N/A')
            pipeline_number = result.get('number', 'N/A')
            circleci_logger.info("Pipeline触发成功!")
            circleci_logger.info(f"Pipeline ID: {pipeline_id}")
            circleci_logger.info(f"Pipeline Number: {pipeline_number}")
            return {
                'success': True,
                'pipeline_id': pipeline_id,
                'pipeline_number': pipeline_number,
                'status_code': response.status_code
            }
        elif response.status_code == 404:
            circleci_logger.error("404错误 - 项目未找到")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': '项目未找到或无权访问'
            }
        elif response.status_code == 401:
            circleci_logger.error("401错误 - 认证失败")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': 'API Token认证失败'
            }
        elif response.status_code == 403:
            circleci_logger.error("403错误 - 权限不足")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': 'API Token权限不足'
            }
        else:
            circleci_logger.error(f"请求失败，状态码: {response.status_code}")
            circleci_logger.debug(f"响应内容: {response.text}")
            return {
                'success': False,
                'pipeline_id': None,
                'pipeline_number': None,
                'status_code': response.status_code,
                'error': f'请求失败: {response.text}'
            }

    except requests.exceptions.Timeout as e:
        circleci_logger.error(f"请求超时: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': '请求超时，请检查网络连接'
        }
    except requests.exceptions.RequestException as e:
        circleci_logger.error(f"网络请求错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': f'网络请求错误: {str(e)}'
        }
    except json.JSONDecodeError as e:
        circleci_logger.error(f"JSON解析错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': 'JSON解析错误'
        }
    except Exception as e:
        circleci_logger.error(f"未知错误: {e}")
        return {
            'success': False,
            'pipeline_id': None,
            'pipeline_number': None,
            'error': f'未知错误: {str(e)}'
        }

def validate_project_slug(project_slug: str) -> bool:
    """
    验证项目slug格式

    Args:
        project_slug (str): 项目slug

    Returns:
        bool: 验证是否通过
    """
    circleci_logger.info("验证项目配置...")
    circleci_logger.info(f"当前项目slug: {project_slug}")

    if '/' not in project_slug or project_slug.count('/') != 2:
        circleci_logger.error("项目slug格式错误")
        circleci_logger.error("正确格式应该是: vcs-type/org-name/repo-name")
        circleci_logger.error("例如: github/your-org/your-repo")
        return False

    vcs_type, org_name, repo_name = project_slug.split('/')
    circleci_logger.info(f"VCS类型: {vcs_type}")
    circleci_logger.info(f"组织名: {org_name}")
    circleci_logger.info(f"仓库名: {repo_name}")

    if vcs_type not in ['github', 'bitbucket']:
        circleci_logger.error("不支持的VCS类型，只支持github和bitbucket")
        return False

    return True

def setup_argument_parser() -> argparse.ArgumentParser:
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

def show_current_config() -> None:
    circleci_logger.info("当前配置信息:")
    circleci_logger.info("=" * 50)
    circleci_logger.info(f"项目Slug: {PROJECT_SLUG}")
    circleci_logger.info(f"分支名称: {BRANCH}")
    token = get_headers().get('Circle-Token', '')
    circleci_logger.info(f"API Token: {'已配置' if token else '未配置'}")
    circleci_logger.info("=" * 50)

def main() -> None:
    parser = setup_argument_parser()
    args = parser.parse_args()

    circleci_logger.info("CircleCI Pipeline触发器")
    circleci_logger.info("=" * 50)

    if args.list_config:
        show_current_config()
        return

    project_slug = args.project or PROJECT_SLUG
    branch = args.branch or BRANCH

    if args.project or args.branch:
        circleci_logger.info("使用参数:")
        if args.project:
            circleci_logger.info(f"  项目: {project_slug} (命令行指定)")
        else:
            circleci_logger.info(f"  项目: {project_slug} (配置文件默认值)")

        if args.branch:
            circleci_logger.info(f"  分支: {branch} (命令行指定)")
        else:
            circleci_logger.info(f"  分支: {branch} (配置文件默认值)")

    if not validate_project_slug(project_slug):
        circleci_logger.warning("解决方案:")
        circleci_logger.warning("1. 使用 -p 参数指定正确的项目slug")
        circleci_logger.warning("2. 修改config.py中的PROJECT_SLUG")
        circleci_logger.warning("3. 检查项目是否存在于CircleCI中")
        sys.exit(1)

    result = trigger_circleci_pipeline(project_slug, branch)

    if isinstance(result, bool):
        success = result
    else:
        success = result.get('success', False)

    if not success:
        circleci_logger.warning("故障排除建议:")
        circleci_logger.warning("1. 检查项目slug格式是否正确")
        circleci_logger.warning("2. 验证API token是否有效")
        circleci_logger.warning("3. 确认项目在CircleCI中已配置")
        circleci_logger.warning("4. 检查API token权限")
        circleci_logger.warning("5. 使用 --list-config 查看当前配置")

if __name__ == "__main__":
    main()
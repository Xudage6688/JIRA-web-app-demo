from typing import Dict, Any, Optional, List, Tuple
import requests
import time
import sys
from circleCi.config_loader import get_headers, CIRCLECI_API_BASE_URL
from modules.logging_config import circleci_logger


def get_pipeline_status(pipeline_id: str, silent: bool = False, api_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    获取pipeline状态

    Args:
        pipeline_id (str): Pipeline ID
        silent (bool): 如果为True，不打印错误信息（用于监控循环中）
        api_token (str): CircleCI API Token（如果不提供则使用配置文件中的）

    Returns:
        dict: Pipeline状态信息，如果失败返回None
    """
    url = f"{CIRCLECI_API_BASE_URL}/pipeline/{pipeline_id}"
    headers = get_headers(api_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            if not silent:
                circleci_logger.error(f"Pipeline未找到: {pipeline_id}")
            return None
        elif response.status_code == 401:
            if not silent:
                circleci_logger.error("401错误 - 认证失败，请检查API token")
            return None
        elif response.status_code == 403:
            if not silent:
                circleci_logger.error("403错误 - 权限不足")
            return None
        else:
            if not silent:
                circleci_logger.error(f"获取pipeline状态失败，状态码: {response.status_code}")
                circleci_logger.debug(f"响应内容: {response.text}")
            return None

    except requests.exceptions.Timeout:
        if not silent:
            circleci_logger.warning("请求超时，请检查网络连接")
        return None
    except requests.exceptions.RequestException as e:
        if not silent:
            circleci_logger.error(f"网络请求错误: {e}")
        return None
    except Exception as e:
        if not silent:
            circleci_logger.error(f"发生错误: {e}")
        return None


def get_pipeline_workflows(pipeline_id: str, silent: bool = False, api_token: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    """
    获取pipeline下的workflows状态

    Args:
        pipeline_id (str): Pipeline ID
        silent (bool): 如果为True，不打印错误信息
        api_token (str): CircleCI API Token

    Returns:
        list: Workflows列表，如果失败返回None
    """
    url = f"{CIRCLECI_API_BASE_URL}/pipeline/{pipeline_id}/workflow"
    headers = get_headers(api_token)

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get('items', [])
        elif response.status_code == 404:
            if not silent:
                circleci_logger.error(f"Pipeline workflows未找到: {pipeline_id}")
            return None
        elif response.status_code == 401:
            if not silent:
                circleci_logger.error("401错误 - 认证失败，请检查API token")
            return None
        elif response.status_code == 403:
            if not silent:
                circleci_logger.error("403错误 - 权限不足")
            return None
        else:
            if not silent:
                circleci_logger.error(f"获取workflows失败，状态码: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        if not silent:
            circleci_logger.warning("请求超时，请检查网络连接")
        return None
    except requests.exceptions.RequestException as e:
        if not silent:
            circleci_logger.error(f"网络请求错误: {e}")
        return None
    except Exception as e:
        if not silent:
            circleci_logger.error(f"发生错误: {e}")
        return None


def get_workflow_status(pipeline_id: str, silent: bool = False, api_token: Optional[str] = None) -> Optional[str]:
    """
    获取pipeline的实际构建状态（通过workflows）
    """
    workflows = get_pipeline_workflows(pipeline_id, silent=silent, api_token=api_token)

    if not workflows or len(workflows) == 0:
        return None

    statuses = [w.get('status', 'unknown') for w in workflows]

    if 'running' in statuses:
        return 'running'
    elif 'on_hold' in statuses:
        return 'on_hold'
    elif len(statuses) > 0:
        return statuses[-1]

    return None


def format_status(status: str) -> Tuple[str, str]:
    """
    格式化状态显示
    """
    status_map = {
        'running': ('Running', 'RUNNING'),
        'success': ('Success', 'SUCCESS'),
        'failing': ('Success', 'SUCCESS'),
        'failed': ('Failed', 'FAILED'),
        'error': ('Error', 'ERROR'),
        'canceled': ('Canceled', 'CANCELED'),
        'on_hold': ('On Hold', 'ON_HOLD'),
        'not_run': ('Not Run', 'NOT_RUN'),
        'queued': ('Queued', 'QUEUED'),
        'created': ('Created', 'CREATED'),
    }

    status_lower = status.lower() if status else 'unknown'
    display_text, emoji = status_map.get(status_lower, (status, 'UNKNOWN'))
    return display_text, emoji


def monitor_pipeline(pipeline_id: str, check_interval: int = 5, max_duration: Optional[int] = None) -> Optional[str]:
    """
    持续监控pipeline状态
    """
    circleci_logger.info("=" * 60)
    circleci_logger.info("开始监控Pipeline状态")
    circleci_logger.info("=" * 60)
    circleci_logger.info(f"Pipeline ID: {pipeline_id}")
    circleci_logger.info(f"检查间隔: {check_interval}秒")
    if max_duration:
        circleci_logger.info(f"最大监控时长: {max_duration}秒")
    circleci_logger.info("=" * 60)

    start_time = time.time()
    previous_status = None
    last_status_display_time = start_time
    status_display_interval = 30
    check_count = 0
    final_statuses = ['success', 'failing', 'failed', 'error', 'canceled']

    try:
        while True:
            check_count += 1
            current_time = time.time()
            elapsed_time = int(current_time - start_time)

            if max_duration and elapsed_time > max_duration:
                circleci_logger.warning(f"已达到最大监控时长 ({max_duration}秒)，停止监控")
                break

            pipeline_data = get_pipeline_status(pipeline_id, silent=True)

            if not pipeline_data:
                if check_count == 1 or check_count % 10 == 0:
                    circleci_logger.warning(f"[{time.strftime('%H:%M:%S')}] 无法获取pipeline状态，{check_interval}秒后重试... (第{check_count}次检查)")
                time.sleep(check_interval)
                continue

            pipeline_number = pipeline_data.get('number', 'N/A')
            pipeline_state = pipeline_data.get('state', 'unknown')

            workflow_status = get_workflow_status(pipeline_id, silent=True)

            if workflow_status:
                current_status = workflow_status
            else:
                current_status = pipeline_state

            should_display = (
                current_status != previous_status or
                (current_time - last_status_display_time) >= status_display_interval
            )

            if should_display:
                display_text, emoji = format_status(current_status)
                circleci_logger.info(f"[{time.strftime('%H:%M:%S')}] [{emoji}] 状态: {display_text} (Pipeline #{pipeline_number})")
                circleci_logger.info(f"         已运行时间: {elapsed_time}秒 ({elapsed_time // 60}分{elapsed_time % 60}秒) | 检查次数: {check_count}")

                previous_status = current_status
                last_status_display_time = current_time

            if current_status in final_statuses:
                display_text, emoji = format_status(current_status)
                total_time = int(time.time() - start_time)

                circleci_logger.info("=" * 60)
                circleci_logger.info(f"[{emoji}] Pipeline已完成")
                circleci_logger.info("=" * 60)
                circleci_logger.info(f"最终状态: {display_text}")
                circleci_logger.info(f"Pipeline ID: {pipeline_id}")
                circleci_logger.info(f"Pipeline Number: {pipeline_number}")
                circleci_logger.info(f"总耗时: {total_time}秒 ({total_time // 60}分{total_time % 60}秒)")
                circleci_logger.info(f"总检查次数: {check_count}")
                circleci_logger.info("=" * 60)

                return current_status

            time.sleep(check_interval)

    except KeyboardInterrupt:
        circleci_logger.warning("用户中断监控")
        if previous_status:
            display_text, emoji = format_status(previous_status)
            circleci_logger.info(f"当前状态: [{emoji}] {display_text}")
        return previous_status
    except Exception as e:
        circleci_logger.error(f"监控过程中发生错误: {e}")
        return None


def get_pipeline_id_by_number(project_slug: str, pipeline_number: int, api_token: Optional[str] = None) -> Optional[str]:
    """
    通过pipeline number查找pipeline ID
    """
    url = f"{CIRCLECI_API_BASE_URL}/project/{project_slug}/pipeline"
    headers = get_headers(api_token)

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])

            for pipeline in items:
                if pipeline.get('number') == pipeline_number:
                    return pipeline.get('id')

            return None
        else:
            return None

    except Exception as e:
        return None


def monitor_by_pipeline_number(project_slug: str, pipeline_number: int, check_interval: int = 5, max_duration: Optional[int] = None, api_token: Optional[str] = None) -> Optional[str]:
    """
    通过pipeline number监控（需要先获取pipeline ID）
    """
    url = f"{CIRCLECI_API_BASE_URL}/project/{project_slug}/pipeline"
    headers = get_headers(api_token)

    try:
        response = requests.get(url, headers=headers, params={'page-token': ''})

        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])

            for pipeline in items:
                if pipeline.get('number') == pipeline_number:
                    pipeline_id = pipeline.get('id')
                    return monitor_pipeline(pipeline_id, check_interval, max_duration)

            circleci_logger.error(f"未找到Pipeline #{pipeline_number}")
            return None
        else:
            circleci_logger.error(f"获取pipelines列表失败，状态码: {response.status_code}")
            return None

    except Exception as e:
        circleci_logger.error(f"发生错误: {e}")
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="CircleCI Pipeline状态监控工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python monitoring.py -i <pipeline-id>                    # 通过Pipeline ID监控
  python monitoring.py -n <pipeline-number> -p <project>   # 通过Pipeline Number监控
  python monitoring.py -i <pipeline-id> -i 5              # 设置检查间隔为5秒
  python monitoring.py -i <pipeline-id> -m 3600           # 设置最大监控时长为1小时
        """
    )

    parser.add_argument(
        '-i', '--pipeline-id',
        type=str,
        help='Pipeline ID（优先使用此参数）'
    )

    parser.add_argument(
        '-n', '--pipeline-number',
        type=int,
        help='Pipeline Number（需要配合--project使用）'
    )

    parser.add_argument(
        '-p', '--project',
        type=str,
        help='项目slug（格式: vcs-type/org-name/repo-name），配合--pipeline-number使用'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=10,
        help='检查间隔（秒），默认10秒'
    )

    parser.add_argument(
        '-m', '--max-duration',
        type=int,
        help='最大监控时长（秒），默认无限制'
    )

    args = parser.parse_args()

    if args.pipeline_id:
        monitor_pipeline(args.pipeline_id, args.interval, args.max_duration)
    elif args.pipeline_number and args.project:
        monitor_by_pipeline_number(args.project, args.pipeline_number, args.interval, args.max_duration)
    else:
        circleci_logger.error("错误: 必须提供以下参数之一:")
        circleci_logger.error("  1. --pipeline-id (-i) <pipeline-id>")
        circleci_logger.error("  2. --pipeline-number (-n) <number> 和 --project (-p) <project-slug>")
        circleci_logger.error("使用 --help 查看详细帮助")
        sys.exit(1)


if __name__ == "__main__":
    main()
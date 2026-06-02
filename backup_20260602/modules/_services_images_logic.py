"""
Services Images 反向查询业务逻辑

纯函数模块，用于单元测试和复用。
提取自 pages/2_🐳_Services_Images_Extractor.py

功能：
- calculateRemainingServices: 计算剩余服务列表
- checkMasterBranch: 检查镜像版本是否为 master 分支
- highlightNonMaster: 生成 DataFrame 高亮样式
"""

from typing import Any, Union, Optional, List, Tuple, Dict
import pandas as pd


def calculateRemainingServices(
    all_services: List[str],
    selected_services: List[str],
) -> List[str]:
    """
    计算剩余服务列表（所有服务 - 已选择服务）。

    用于反向查询：从全部服务中排除已选择的发版服务，
    得到剩余的非发版服务列表。

    Args:
        all_services: 从 circleci-services.txt 加载的全部服务
        selected_services: 用户选择的发版服务列表

    Returns:
        剩余服务列表（保持原有顺序）

    Examples:
        >>> calculateRemainingServices(['a', 'b', 'c'], ['b'])
        ['a', 'c']
        >>> calculateRemainingServices(['a', 'b', 'c'], [])
        ['a', 'b', 'c']
        >>> calculateRemainingServices(['a', 'b', 'c'], ['a', 'b', 'c'])
        []
    """
    selected_set = set(selected_services)
    return [s for s in all_services if s not in selected_set]


def checkMasterBranch(version: Optional[str]) -> Tuple[bool, str]:
    """
    检查镜像版本是否为 master 分支。

    用于发版前验证：非 master 分支的服务需要关注，
    避免回归测试在错误的分支上进行。

    判断规则：
    - 以 "master" 开头（如 master-1.12.99-fff34a049）
    - 包含 "master-"（如 app-master-1.0.0）
    - 空值或 "N/A" 视为未知

    Args:
        version: 镜像标签字符串（如 'master-1.12.99-fff34a049'）

    Returns:
        (is_master, status_icon): 是否为 master 分支和状态图标
        - (True, '✅'): master 分支
        - (False, '⚠️'): 非 master 分支
        - (False, '❓'): 未知/查询失败

    Examples:
        >>> checkMasterBranch('master-1.12.99-fff34a049')
        (True, '✅')
        >>> checkMasterBranch('feature-xyz')
        (False, '⚠️')
        >>> checkMasterBranch(None)
        (False, '❓')
    """
    if not version or version == 'N/A':
        return False, '❓'
    version_lower = version.lower()
    if version_lower.startswith('master') or 'master-' in version_lower:
        return True, '✅'
    return False, '⚠️'


def highlightNonMaster(row: Union[Dict[str, Any], 'pd.Series']) -> List[str]:
    """
    为 DataFrame 行生成高亮样式。

    非 master 分支的服务以黄色背景高亮显示。

    Args:
        row: DataFrame 行数据，需包含 'is_master' 字段

    Returns:
        CSS 样式列表，应用于整行

    Examples:
        >>> highlightNonMaster({'is_master': False, 'service': 'a'})
        ['background-color: #fff3cd; color: #856404', 'background-color: #fff3cd; color: #856404']
        >>> highlightNonMaster({'is_master': True, 'service': 'a'})
        ['', '']
    """
    if not row.get('is_master', True):
        return ['background-color: #fff3cd; color: #856404'] * len(row)
    return [''] * len(row)


def countNonMasterServices(details: List[Dict[str, Any]]) -> int:
    """
    统计非 master 分支服务数量。

    Args:
        details: 服务详情列表，每项包含 'is_master' 字段

    Returns:
        非 master 服务数量

    Examples:
        >>> countNonMasterServices([{'is_master': True}, {'is_master': False}])
        1
    """
    return sum(1 for d in details if not d.get('is_master', True))


if __name__ == '__main__':
    print("测试 calculateRemainingServices:")
    assert calculateRemainingServices(['a', 'b', 'c'], ['b']) == ['a', 'c']
    print("  ✅ 基本测试通过")

    print("\n测试 checkMasterBranch:")
    assert checkMasterBranch('master-1.12.99-fff34a049') == (True, '✅')
    assert checkMasterBranch('feature-xyz') == (False, '⚠️')
    assert checkMasterBranch(None) == (False, '❓')
    print("  ✅ 基本测试通过")

    print("\n所有测试通过!")

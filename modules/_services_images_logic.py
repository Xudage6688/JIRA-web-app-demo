"""
Services Images 反向查询业务逻辑

纯函数模块，用于单元测试和复用。
提取自 pages/2_🐳_Services_Images_Extractor.py

功能：
- calculateRemainingServices: 计算剩余服务列表
- checkMasterBranch: 检查镜像版本是否为 master 分支（兼容旧接口）
- checkBranchStatus: 检查镜像版本分支类型（master/release/other/unknown）
- highlightNonMaster: 生成 DataFrame 高亮样式（兼容旧接口）
- highlightBranchStatus: 按分支类型生成 DataFrame 高亮样式
- countNonMasterServices: 统计非 master 分支服务数量（兼容旧接口）
- countAttentionServices: 统计需关注的服务数量（非 master 且非 release）
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


def checkBranchStatus(version: Optional[str]) -> Tuple[str, str, str]:
    """
    检查镜像版本的分支类型。

    用于发版前验证：非 master 且非 release 分支的服务需要关注，
    避免回归测试在错误的分支上进行。

    判断规则：
    - 以 "master" 开头或包含 "master-" → master 分支
    - 以 "release" 开头或包含 "release-" → release 分支
    - 空值或 "N/A" → unknown
    - 其他 → other

    Args:
        version: 镜像标签字符串（如 'master-1.12.99-fff34a049'）

    Returns:
        (branch_type, status_icon, status_text):
        - branch_type: 'master' | 'release' | 'other' | 'unknown'
        - status_icon: '✅' | '🏷️' | '⚠️' | '❓'
        - status_text: 'master' | 'release' | '非master' | '未知'

    Examples:
        >>> checkBranchStatus('master-1.12.99-fff34a049')
        ('master', '✅', 'master')
        >>> checkBranchStatus('release-1.0.0')
        ('release', '🏷️', 'release')
        >>> checkBranchStatus('feature-xyz')
        ('other', '⚠️', '非master')
        >>> checkBranchStatus(None)
        ('unknown', '❓', '未知')
    """
    if not version or version == 'N/A':
        return 'unknown', '❓', '未知'
    version_lower = version.lower()
    if version_lower.startswith('master') or 'master-' in version_lower:
        return 'master', '✅', 'master'
    if version_lower.startswith('release') or 'release-' in version_lower:
        return 'release', '🏷️', 'release'
    return 'other', '⚠️', '非master'


def checkMasterBranch(version: Optional[str]) -> Tuple[bool, str]:
    """
    检查镜像版本是否为 master 分支（兼容旧接口）。

    推荐使用 checkBranchStatus() 获取完整的分支类型信息。

    Args:
        version: 镜像标签字符串

    Returns:
        (is_master, status_icon): 是否为 master 分支和状态图标

    Examples:
        >>> checkMasterBranch('master-1.12.99-fff34a049')
        (True, '✅')
        >>> checkMasterBranch('release-1.0.0')
        (False, '🏷️')
        >>> checkMasterBranch('feature-xyz')
        (False, '⚠️')
    """
    branch_type, status_icon, _ = checkBranchStatus(version)
    return branch_type == 'master', status_icon


def highlightBranchStatus(row: Union[Dict[str, Any], 'pd.Series']) -> List[str]:
    """
    为 DataFrame 行生成高亮样式（按分支类型）。

    - master/release 分支：无高亮（视为正常）
    - other（非master非release）：黄色背景高亮（需关注）
    - unknown：无高亮

    Args:
        row: DataFrame 行数据，需包含 'branch_type' 或 'is_master' 字段

    Returns:
        CSS 样式列表，应用于整行

    Examples:
        >>> highlightBranchStatus({'branch_type': 'other', 'service': 'a'})
        ['background-color: #fff3cd; color: #856404', 'background-color: #fff3cd; color: #856404']
        >>> highlightBranchStatus({'branch_type': 'release', 'service': 'a'})
        ['', '']
    """
    branch_type = row.get('branch_type')
    if branch_type:
        if branch_type == 'other':
            return ['background-color: #fff3cd; color: #856404'] * len(row)
        return [''] * len(row)
    # 兼容旧字段 is_master
    if not row.get('is_master', True):
        return ['background-color: #fff3cd; color: #856404'] * len(row)
    return [''] * len(row)


def highlightNonMaster(row: Union[Dict[str, Any], 'pd.Series']) -> List[str]:
    """
    为 DataFrame 行生成高亮样式（兼容旧接口）。

    推荐使用 highlightBranchStatus()。

    Args:
        row: DataFrame 行数据，需包含 'is_master' 或 'branch_type' 字段

    Returns:
        CSS 样式列表，应用于整行
    """
    return highlightBranchStatus(row)


def countAttentionServices(details: List[Dict[str, Any]]) -> int:
    """
    统计需关注的服务数量（非 master 且非 release）。

    Args:
        details: 服务详情列表，每项包含 'branch_type' 或 'is_master' 字段

    Returns:
        需关注的服务数量

    Examples:
        >>> countAttentionServices([{'branch_type': 'other'}])
        1
        >>> countAttentionServices([{'branch_type': 'master'}, {'branch_type': 'release'}])
        0
        >>> countAttentionServices([{'branch_type': 'master'}, {'branch_type': 'other'}])
        1
    """
    count = 0
    for d in details:
        branch_type = d.get('branch_type')
        if branch_type:
            if branch_type == 'other':
                count += 1
        else:
            # 兼容旧字段 is_master（假设 release 也被记录为 is_master=False）
            # 但旧接口下无法区分 release 和 other，统一按非 master 统计
            if not d.get('is_master', True):
                count += 1
    return count


def countNonMasterServices(details: List[Dict[str, Any]]) -> int:
    """
    统计非 master 分支服务数量（兼容旧接口）。

    推荐使用 countAttentionServices() 统计需关注的服务。

    Args:
        details: 服务详情列表，每项包含 'is_master' 或 'branch_type' 字段

    Returns:
        非 master 服务数量（含 release 和 other）

    Examples:
        >>> countNonMasterServices([{'is_master': True}, {'is_master': False}])
        1
    """
    return sum(1 for d in details if not d.get('is_master', True))


if __name__ == '__main__':
    # 简单测试
    print("测试 calculateRemainingServices:")
    assert calculateRemainingServices(['a', 'b', 'c'], ['b']) == ['a', 'c']
    print("  ✅ 基本测试通过")

    print("\n测试 checkBranchStatus:")
    assert checkBranchStatus('master-1.12.99-fff34a049') == ('master', '✅', 'master')
    assert checkBranchStatus('release-1.0.0') == ('release', '🏷️', 'release')
    assert checkBranchStatus('feature-xyz') == ('other', '⚠️', '非master')
    assert checkBranchStatus(None) == ('unknown', '❓', '未知')
    print("  ✅ 基本测试通过")

    print("\n测试 checkMasterBranch (兼容旧接口):")
    assert checkMasterBranch('master-1.12.99-fff34a049') == (True, '✅')
    assert checkMasterBranch('release-1.0.0') == (False, '🏷️')
    assert checkMasterBranch('feature-xyz') == (False, '⚠️')
    assert checkMasterBranch(None) == (False, '❓')
    print("  ✅ 基本测试通过")

    print("\n所有测试通过!")

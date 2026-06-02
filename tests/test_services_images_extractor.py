"""
单元测试：Services Images Extractor 反向查询功能

测试核心函数（从 modules/_services_images_logic.py 导入）：
- calculateRemainingServices: 计算剩余服务列表
- checkBranchStatus: 检查镜像版本分支类型
- checkMasterBranch: 检查镜像版本是否为 master 分支（兼容旧接口）
- countAttentionServices: 统计需关注的服务数量
"""

import pytest
import sys
import os

# 添加 modules 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules._services_images_logic import (
    calculateRemainingServices,
    checkBranchStatus,
    checkMasterBranch,
    countAttentionServices,
    countNonMasterServices,
)


# ========== 测试用例 ==========

class TestCalculateRemainingServices:
    """测试 calculateRemainingServices 函数"""

    def test_empty_selected_returns_all(self):
        """测试：未选择任何服务时，剩余服务 = 全部服务"""
        all_services = ['a', 'b', 'c']
        selected = []
        result = calculateRemainingServices(all_services, selected)
        assert result == ['a', 'b', 'c']

    def test_full_selected_returns_empty(self):
        """测试：选择全部服务时，剩余服务 = 空"""
        all_services = ['a', 'b', 'c']
        selected = ['a', 'b', 'c']
        result = calculateRemainingServices(all_services, selected)
        assert result == []

    def test_partial_selected_returns_correct_remaining(self):
        """测试：选择部分服务时，计算正确的剩余服务"""
        all_services = ['a', 'b', 'c', 'd', 'e']
        selected = ['b', 'd']
        result = calculateRemainingServices(all_services, selected)
        assert result == ['a', 'c', 'e']

    def test_order_preserved(self):
        """测试：剩余服务保持原有顺序"""
        all_services = ['service1', 'service2', 'service3']
        selected = ['service2']
        result = calculateRemainingServices(all_services, selected)
        assert result == ['service1', 'service3']
        assert result[0] == 'service1'
        assert result[1] == 'service3'

    def test_duplicate_handling(self):
        """测试：重复服务名正确处理"""
        all_services = ['a', 'b', 'a', 'c']
        selected = ['a']
        result = calculateRemainingServices(all_services, selected)
        # 列表中保留重复，但 selected 是集合去重
        assert result == ['b', 'c']

    def test_selected_not_in_all_services(self):
        """测试：选择的服务不在全部服务列表中"""
        all_services = ['a', 'b', 'c']
        selected = ['d', 'e']
        result = calculateRemainingServices(all_services, selected)
        assert result == ['a', 'b', 'c']

    def test_large_service_list(self):
        """测试：大服务列表（模拟 circleci-services.txt 74个服务）"""
        all_services = [f'service{i}' for i in range(1, 75)]
        selected = ['service1', 'service10', 'service50']
        result = calculateRemainingServices(all_services, selected)
        assert len(result) == 71
        assert 'service1' not in result
        assert 'service10' not in result
        assert 'service50' not in result


class TestCheckMasterBranch:
    """测试 checkMasterBranch 函数（兼容旧接口）"""

    def test_master_prefix(self):
        """测试：master 开头的版本识别"""
        is_master, icon = checkMasterBranch('master-1.12.99-fff34a049')
        assert is_master == True
        assert icon == '✅'

    def test_master_exact(self):
        """测试：精确 master 版本"""
        is_master, icon = checkMasterBranch('master')
        assert is_master == True
        assert icon == '✅'

    def test_master_in_middle(self):
        """测试：master 在版本中间"""
        is_master, icon = checkMasterBranch('app-master-1.0.0')
        assert is_master == True
        assert icon == '✅'

    def test_release_branch(self):
        """测试：release 分支识别"""
        is_master, icon = checkMasterBranch('release-1.0.0')
        assert is_master == False
        assert icon == '🏷️'

    def test_feature_branch(self):
        """测试：feature 分支识别为非 master"""
        is_master, icon = checkMasterBranch('feature-xyz-abc123')
        assert is_master == False
        assert icon == '⚠️'

    def test_empty_version(self):
        """测试：空版本处理"""
        is_master, icon = checkMasterBranch('')
        assert is_master == False
        assert icon == '❓'

    def test_na_version(self):
        """测试：N/A 版本处理"""
        is_master, icon = checkMasterBranch('N/A')
        assert is_master == False
        assert icon == '❓'

    def test_none_version(self):
        """测试：None 版本处理"""
        is_master, icon = checkMasterBranch(None)
        assert is_master == False
        assert icon == '❓'


class TestCheckBranchStatus:
    """测试 checkBranchStatus 函数（新接口）"""

    def test_master_prefix(self):
        """测试：master 开头的版本"""
        branch_type, icon, text = checkBranchStatus('master-1.12.99-fff34a049')
        assert branch_type == 'master'
        assert icon == '✅'
        assert text == 'master'

    def test_master_exact(self):
        """测试：精确 master 版本"""
        branch_type, icon, text = checkBranchStatus('master')
        assert branch_type == 'master'
        assert icon == '✅'
        assert text == 'master'

    def test_master_in_middle(self):
        """测试：master 在版本中间"""
        branch_type, icon, text = checkBranchStatus('app-master-1.0.0')
        assert branch_type == 'master'
        assert icon == '✅'
        assert text == 'master'

    def test_release_prefix(self):
        """测试：release 开头的版本"""
        branch_type, icon, text = checkBranchStatus('release-1.0.0')
        assert branch_type == 'release'
        assert icon == '🏷️'
        assert text == 'release'

    def test_release_exact(self):
        """测试：精确 release 版本"""
        branch_type, icon, text = checkBranchStatus('release')
        assert branch_type == 'release'
        assert icon == '🏷️'
        assert text == 'release'

    def test_release_in_middle(self):
        """测试：release 在版本中间"""
        branch_type, icon, text = checkBranchStatus('app-release-1.0.0')
        assert branch_type == 'release'
        assert icon == '🏷️'
        assert text == 'release'

    def test_feature_branch(self):
        """测试：feature 分支为 other"""
        branch_type, icon, text = checkBranchStatus('feature-xyz')
        assert branch_type == 'other'
        assert icon == '⚠️'
        assert text == '非master'

    def test_dev_branch(self):
        """测试：dev 分支为 other"""
        branch_type, icon, text = checkBranchStatus('dev-latest')
        assert branch_type == 'other'
        assert icon == '⚠️'
        assert text == '非master'

    def test_empty_version(self):
        """测试：空版本为 unknown"""
        branch_type, icon, text = checkBranchStatus('')
        assert branch_type == 'unknown'
        assert icon == '❓'
        assert text == '未知'

    def test_na_version(self):
        """测试：N/A 版本为 unknown"""
        branch_type, icon, text = checkBranchStatus('N/A')
        assert branch_type == 'unknown'
        assert icon == '❓'
        assert text == '未知'

    def test_none_version(self):
        """测试：None 版本为 unknown"""
        branch_type, icon, text = checkBranchStatus(None)
        assert branch_type == 'unknown'
        assert icon == '❓'
        assert text == '未知'

    def test_version_with_uppercase_master(self):
        """测试：MASTER 大写版本识别"""
        branch_type, icon, text = checkBranchStatus('MASTER-1.0.0')
        assert branch_type == 'master'
        assert icon == '✅'

    def test_version_with_uppercase_release(self):
        """测试：RELEASE 大写版本识别"""
        branch_type, icon, text = checkBranchStatus('RELEASE-1.0.0')
        assert branch_type == 'release'
        assert icon == '🏷️'


class TestCountAttentionServices:
    """测试 countAttentionServices 函数"""

    def test_all_master(self):
        """测试：全部为 master 分支"""
        details = [
            {'service': 'a', 'branch_type': 'master'},
            {'service': 'b', 'branch_type': 'master'},
        ]
        assert countAttentionServices(details) == 0

    def test_all_release(self):
        """测试：全部为 release 分支"""
        details = [
            {'service': 'a', 'branch_type': 'release'},
            {'service': 'b', 'branch_type': 'release'},
        ]
        assert countAttentionServices(details) == 0

    def test_all_other(self):
        """测试：全部为 other 分支"""
        details = [
            {'service': 'a', 'branch_type': 'other'},
            {'service': 'b', 'branch_type': 'other'},
        ]
        assert countAttentionServices(details) == 2

    def test_mixed(self):
        """测试：混合情况"""
        details = [
            {'service': 'a', 'branch_type': 'master'},
            {'service': 'b', 'branch_type': 'release'},
            {'service': 'c', 'branch_type': 'other'},
            {'service': 'd', 'branch_type': 'unknown'},
        ]
        assert countAttentionServices(details) == 1

    def test_empty(self):
        """测试：空列表"""
        assert countAttentionServices([]) == 0


class TestIntegration:
    """集成测试：反向查询场景"""

    def test_weekly_release_scenario(self):
        """测试：每周一发版场景模拟

        场景：选择10个发版服务，反向查询剩余64个服务，
        验证它们是否都是 master 分支
        """
        # 模拟 74 个全部服务
        all_services = [f'service{i}' for i in range(1, 75)]

        # 选择10个发版服务
        release_services = ['service1', 'service10', 'service20', 'service30',
                            'service40', 'service50', 'service60', 'service70',
                            'service5', 'service15']

        # 计算剩余服务
        remaining = calculateRemainingServices(all_services, release_services)
        assert len(remaining) == 64

        # 模拟镜像版本（部分 master，部分非 master）
        sample_versions = {
            'service2': 'master-1.0.0-abc',
            'service3': 'feature-fix-123',  # 非 master
            'service4': 'master-2.0.0-def',
            'service6': 'dev-latest',  # 非 master
        }

        # 验证分支状态
        non_master_found = []
        for svc, version in sample_versions.items():
            if svc in remaining:
                is_master, _ = checkMasterBranch(version)
                if not is_master:
                    non_master_found.append(svc)

        assert 'service3' in non_master_found
        assert 'service6' in non_master_found
        assert len(non_master_found) == 2


class TestCountNonMasterServices:
    """测试 countNonMasterServices 函数"""

    def test_all_master(self):
        """测试：全部为 master 分支"""
        details = [
            {'service': 'a', 'is_master': True},
            {'service': 'b', 'is_master': True},
        ]
        assert countNonMasterServices(details) == 0

    def test_all_non_master(self):
        """测试：全部为非 master 分支"""
        details = [
            {'service': 'a', 'is_master': False},
            {'service': 'b', 'is_master': False},
        ]
        assert countNonMasterServices(details) == 2

    def test_mixed(self):
        """测试：混合情况"""
        details = [
            {'service': 'a', 'is_master': True},
            {'service': 'b', 'is_master': False},
            {'service': 'c', 'is_master': True},
            {'service': 'd', 'is_master': False},
        ]
        assert countNonMasterServices(details) == 2

    def test_empty(self):
        """测试：空列表"""
        assert countNonMasterServices([]) == 0

    def test_missing_field(self):
        """测试：缺少 is_master 字段时默认为 True"""
        details = [
            {'service': 'a'},  # 缺少 is_master
            {'service': 'b', 'is_master': False},
        ]
        assert countNonMasterServices(details) == 1
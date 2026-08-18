"""监控 Tab 自动审批 Preprod 逻辑单元测试"""
from circleCi.auto_approve import (
    ACTIVE_WORKFLOW_STATUSES,
    PREPROD_DEPLOY_JOB_SUBSTR,
    PREPROD_AUTO_POLLING,
    PREPROD_AUTO_DEPLOY_SUCCESS,
    PREPROD_AUTO_DEPLOY_FAILED,
    PREPROD_AUTO_IDLE,
    find_pending_preprod_approvals,
    auto_approve_jobs,
    has_active_workflows,
    has_pending_preprod_work,
    get_preprod_auto_mode_status,
)


def _wf(wf_id, name='build-and-deploy', status='on_hold'):
    return {'id': wf_id, 'name': name, 'status': status}


def _job(job_id, name, job_type='approval', status='on_hold', req_id=None):
    return {
        'id': job_id,
        'name': name,
        'type': job_type,
        'status': status,
        'approval_request_id': req_id or f'req-{job_id}',
    }


class TestFindPendingPreprodApprovals:
    """测试 find_pending_preprod_approvals"""

    def test_matches_preprod_on_hold_approval(self):
        workflows = [_wf('wf1')]
        jobs_map = {'wf1': [_job('j1', 'approve-deploy-preprod')]}
        result = find_pending_preprod_approvals(workflows, jobs_map)
        assert len(result) == 1
        assert result[0]['id'] == 'j1'

    def test_attaches_workflow_info(self):
        workflows = [_wf('wf1', name='deploy-workflow')]
        jobs_map = {'wf1': [_job('j1', 'approve-preprod')]}
        result = find_pending_preprod_approvals(workflows, jobs_map)
        assert result[0]['_workflow_id'] == 'wf1'
        assert result[0]['_workflow_name'] == 'deploy-workflow'

    def test_excludes_non_preprod_jobs(self):
        workflows = [_wf('wf1')]
        jobs_map = {'wf1': [_job('j1', 'approve-deploy-prod')]}
        assert find_pending_preprod_approvals(workflows, jobs_map) == []

    def test_excludes_approved_jobs(self):
        workflows = [_wf('wf1')]
        jobs_map = {'wf1': [_job('j1', 'approve-preprod', status='success')]}
        assert find_pending_preprod_approvals(workflows, jobs_map) == []

    def test_excludes_build_type_jobs(self):
        workflows = [_wf('wf1')]
        jobs_map = {'wf1': [_job('j1', 'deploy-preprod', job_type='build', status='on_hold')]}
        assert find_pending_preprod_approvals(workflows, jobs_map) == []

    def test_matches_case_insensitive(self):
        workflows = [_wf('wf1')]
        jobs_map = {'wf1': [_job('j1', 'Approve-PreProd-CN')]}
        assert len(find_pending_preprod_approvals(workflows, jobs_map)) == 1

    def test_multiple_workflows(self):
        workflows = [_wf('wf1'), _wf('wf2')]
        jobs_map = {
            'wf1': [_job('j1', 'approve-preprod')],
            'wf2': [_job('j2', 'approve-preprod-2'), _job('j3', 'approve-prod')],
        }
        result = find_pending_preprod_approvals(workflows, jobs_map)
        assert [j['id'] for j in result] == ['j1', 'j2']

    def test_empty_inputs(self):
        assert find_pending_preprod_approvals([], {}) == []
        assert find_pending_preprod_approvals(None, {}) == []


class TestAutoApproveJobs:
    """测试 auto_approve_jobs"""

    def test_approves_each_pending_job(self):
        calls = []

        def fake_approve(wf_id, req_id, api_token=None):
            calls.append((wf_id, req_id, api_token))
            return {'success': True}

        pending = [
            _job('j1', 'approve-preprod', req_id='r1'),
            _job('j2', 'approve-preprod-2', req_id='r2'),
        ]
        pending[0]['_workflow_id'] = 'wf1'
        pending[1]['_workflow_id'] = 'wf1'

        approved, failed = auto_approve_jobs(pending, api_token='tok', approve_fn=fake_approve)

        assert [j['id'] for j in approved] == ['j1', 'j2']
        assert failed == []
        assert calls == [('wf1', 'r1', 'tok'), ('wf1', 'r2', 'tok')]

    def test_collects_failures_with_error(self):
        def fake_approve(wf_id, req_id, api_token=None):
            if req_id == 'r2':
                return {'success': False, 'error': 'permission denied'}
            return {'success': True}

        pending = [
            _job('j1', 'approve-preprod', req_id='r1'),
            _job('j2', 'approve-preprod-2', req_id='r2'),
        ]
        for j in pending:
            j['_workflow_id'] = 'wf1'

        approved, failed = auto_approve_jobs(pending, api_token='tok', approve_fn=fake_approve)

        assert [j['id'] for j in approved] == ['j1']
        assert [j['id'] for j in failed] == ['j2']
        assert failed[0]['_approve_error'] == 'permission denied'

    def test_approve_fn_exception_becomes_failure(self):
        def exploding(wf_id, req_id, api_token=None):
            raise RuntimeError('network down')

        pending = [_job('j1', 'approve-preprod', req_id='r1')]
        pending[0]['_workflow_id'] = 'wf1'

        approved, failed = auto_approve_jobs(pending, api_token='tok', approve_fn=exploding)

        assert approved == []
        assert len(failed) == 1
        assert 'network down' in failed[0]['_approve_error']


class TestHasActiveWorkflows:
    """测试 has_active_workflows"""

    def test_running_is_active(self):
        assert has_active_workflows([_wf('wf1', status='running')]) is True

    def test_on_hold_is_active(self):
        assert has_active_workflows([_wf('wf1', status='on_hold')]) is True

    def test_queued_and_failing_are_active(self):
        assert has_active_workflows([_wf('wf1', status='queued')]) is True
        assert has_active_workflows([_wf('wf1', status='failing')]) is True

    def test_all_terminal_is_inactive(self):
        workflows = [
            _wf('wf1', status='success'),
            _wf('wf2', status='failed'),
            _wf('wf3', status='canceled'),
        ]
        assert has_active_workflows(workflows) is False

    def test_mixed_active_and_terminal(self):
        workflows = [_wf('wf1', status='success'), _wf('wf2', status='running')]
        assert has_active_workflows(workflows) is True

    def test_empty_or_none(self):
        assert has_active_workflows([]) is False
        assert has_active_workflows(None) is False

    def test_active_statuses_constant(self):
        assert ACTIVE_WORKFLOW_STATUSES == {'running', 'queued', 'on_hold', 'failing'}


class TestHasPendingPreprodWork:
    """测试 has_pending_preprod_work（自动轮询停止条件）"""

    def test_pending_preprod_approval(self):
        workflows = [_wf('wf1', status='on_hold')]
        jobs_map = {'wf1': [_job('j1', 'approve-preprod')]}
        assert has_pending_preprod_work(workflows, jobs_map) is True

    def test_deploy_running(self):
        workflows = [_wf('wf1', status='running')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod', status='success'),
                _job('j2', 'deploy-docker-image-on-preprod-aca-new', job_type='build', status='running'),
            ],
        }
        assert has_pending_preprod_work(workflows, jobs_map) is True

    def test_deploy_success_stops_even_if_workflow_active(self):
        """preprod 部署成功后停止，即使 workflow 仍在等待 staging 审批"""
        workflows = [_wf('wf1', status='on_hold')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod', status='success'),
                _job('j2', 'deploy-docker-image-on-preprod-aca-new', job_type='build', status='success'),
                _job('j3', 'approve-staging', status='on_hold'),
            ],
        }
        assert has_pending_preprod_work(workflows, jobs_map) is False

    def test_approval_done_deploy_not_visible_yet(self):
        workflows = [_wf('wf1', status='running')]
        jobs_map = {'wf1': [_job('j1', 'approve-preprod', status='success')]}
        assert has_pending_preprod_work(workflows, jobs_map) is True

    def test_wait_for_preprod_jobs_while_pipeline_active(self):
        workflows = [_wf('wf1', status='running')]
        jobs_map = {'wf1': [_job('j1', 'build', job_type='build', status='running')]}
        assert has_pending_preprod_work(workflows, jobs_map) is True

    def test_pipeline_done_no_preprod(self):
        workflows = [_wf('wf1', status='success')]
        jobs_map = {'wf1': [_job('j1', 'build', job_type='build', status='success')]}
        assert has_pending_preprod_work(workflows, jobs_map) is False

    def test_deploy_failed_stops_polling(self):
        workflows = [_wf('wf1', status='failed')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod', status='success'),
                _job('j2', 'deploy-docker-image-on-preprod-svc', job_type='build', status='failed'),
            ],
        }
        assert has_pending_preprod_work(workflows, jobs_map) is False
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_DEPLOY_FAILED

    def test_deploy_success_status(self):
        workflows = [_wf('wf1', status='on_hold')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod', status='success'),
                _job('j2', 'deploy-docker-image-on-preprod-aca-new', job_type='build', status='success'),
            ],
        }
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_DEPLOY_SUCCESS

    def test_workflow_running_all_deploy_success_keeps_polling(self):
        """第一个 preprod 部署已成功、Workflow 仍在 running 时继续轮询（等待后续部署 Job）"""
        workflows = [_wf('wf1', status='running')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod', status='success'),
                _job('j2', 'deploy-docker-image-on-preprod-a', job_type='build', status='success'),
            ],
        }
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_POLLING

    def test_pipeline_done_no_preprod_is_idle(self):
        workflows = [_wf('wf1', status='success')]
        jobs_map = {'wf1': [_job('j1', 'build', job_type='build', status='success')]}
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_IDLE

    def test_deploy_blocked_before_start_keeps_polling(self):
        """部署 Job 已出现在列表但为 blocked（待审批）时不应误判为部署已完成"""
        workflows = [_wf('wf1', status='on_hold')]
        jobs_map = {
            'wf1': [
                _job('j1', 'approve-preprod'),
                _job(
                    'j2',
                    'deploy-docker-image-on-preprod-aca-new',
                    job_type='build',
                    status='blocked',
                ),
            ],
        }
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_POLLING

    def test_deploy_not_running_without_approval_keeps_polling(self):
        workflows = [_wf('wf1', status='running')]
        jobs_map = {
            'wf1': [
                _job(
                    'j2',
                    'deploy-docker-image-on-preprod-svc',
                    job_type='build',
                    status='not_running',
                ),
            ],
        }
        assert get_preprod_auto_mode_status(workflows, jobs_map) == PREPROD_AUTO_POLLING

    def test_preprod_deploy_substr_constant(self):
        assert PREPROD_DEPLOY_JOB_SUBSTR == 'deploy-docker-image-on-preprod'

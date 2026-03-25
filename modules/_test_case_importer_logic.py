"""
_test_case_importer_logic.py
Test Case 导入核心业务逻辑（纯函数，无 Streamlit 依赖）
所有 HTTP 调用通过可注入的 http_client 参数实现，便于单元测试 mock
"""

import time
from typing import List, Dict, Optional, Tuple, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


# ── HTTP 客户端工厂 ─────────────────────────────────────────────────────────

def _default_http_client():
    import requests
    return requests.Session()


# ── Step 1: Xray 认证 ───────────────────────────────────────────────────────

def authenticate_xray(
    client_id: str,
    client_secret: str,
    http_client=None,
) -> str:
    """
    向 Xray Cloud 认证，获取 Bearer Token。

    Args:
        client_id: Xray Client ID
        client_secret: Xray Client Secret
        http_client: 可选，requests.Session 实例，测试时注入 mock

    Returns:
        Bearer Token 字符串

    Raises:
        XrayAuthError: 认证失败时
    """
    import requests as _req

    client = http_client or _default_http_client()
    resp = client.post(
        "https://xray.cloud.getxray.app/api/v2/authenticate",
        json={"client_id": client_id, "client_secret": client_secret},
        timeout=15,
    )

    if resp.status_code != 200:
        raise XrayAuthError(
            f"Xray 鉴权失败 (状态码: {resp.status_code}): {resp.text[:300]}"
        )

    return resp.text.strip().strip('"')


class XrayAuthError(Exception):
    """Xray 认证失败"""


# ── Step 2: 构建 payload ────────────────────────────────────────────────────

def build_tests_payload(
    df_cases,  # pandas.DataFrame
    selected_sp_team: str,
    selected_priority: str,
    title_mode: str,
    custom_title: str,
) -> List[Dict]:
    """
    将 DataFrame 中的 Test Case 行转换为 Xray API 所需的 JSON payload。

    Args:
        df_cases: 包含 Action / Data / Expected Result 列的 DataFrame
        selected_sp_team: SP Team 名称（如 "Mermaid"）
        selected_priority: Priority（如 "Medium"）
        title_mode: "使用 Action 列作为 Title（推荐）" 或 "自定义统一 Title"
        custom_title: 当 title_mode 为后者时的统一标题

    Returns:
        Xray 格式的 tests payload 列表
    """
    sp_team_field_value = {"value": selected_sp_team}
    tests_payload = []

    for idx, row in df_cases.iterrows():
        action_text = str(row["Action"]).strip()
        data_text = str(row.get("Data", "") or "").strip()
        result_text = str(row["Expected Result"]).strip()

        if title_mode == "自定义统一 Title" and custom_title.strip():
            title = custom_title.strip()
        else:
            title = action_text

        tests_payload.append({
            "fields": {
                "summary": title,
                "project": {"key": "SP"},
                "issuetype": {"name": "Test"},
                "priority": {"name": selected_priority},
                "customfield_12628": sp_team_field_value,
            },
            "xray_test_type": "Manual",
            "steps": [{
                "action": action_text,
                "data": data_text,
                "result": result_text,
            }],
        })

    return tests_payload


# ── Step 3: 批量提交 ────────────────────────────────────────────────────────

def submit_tests_bulk(
    xray_token: str,
    tests_payload: List[Dict],
    http_client=None,
) -> Tuple[Optional[str], List[str]]:
    """
    提交 Test Cases 到 Xray。

    Returns:
        (job_id, created_keys)  — job_id 为 None 时 created_keys 直接可用
    """
    import requests as _req

    client = http_client or _default_http_client()
    headers = {
        "Authorization": f"Bearer {xray_token}",
        "Content-Type": "application/json",
    }

    resp = client.post(
        "https://xray.cloud.getxray.app/api/v2/import/test/bulk",
        headers=headers,
        json=tests_payload,
        timeout=60,
    )

    if resp.status_code not in [200, 201, 202]:
        raise XrayImportError(
            f"Xray 导入请求失败 (状态码: {resp.status_code}): {resp.text[:500]}"
        )

    bulk_result = resp.json()

    # list 响应表示同步返回（无 job_id）；dict 才尝试取 jobId
    if isinstance(bulk_result, list):
        job_id = None
    else:
        job_id = bulk_result.get("jobId") or bulk_result.get("id")

    if not job_id:
        # 同步返回，job_id 为空
        created_keys = []
        if isinstance(bulk_result, list):
            created_keys = [item.get("key") for item in bulk_result if item.get("key")]
        elif bulk_result.get("issues"):
            created_keys = [
                i.get("key") for i in bulk_result["issues"] if i.get("key")
            ]
        return None, created_keys

    return job_id, []


class XrayImportError(Exception):
    """Xray 导入请求失败"""


# ── Step 3b: 轮询 Job 状态 ─────────────────────────────────────────────────

def poll_job_status(
    xray_token: str,
    job_id: str,
    max_polls: int = 30,
    poll_interval: int = 2,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    http_client=None,
) -> List[str]:
    """
    轮询 Xray 批量导入 Job 的完成状态。

    Args:
        xray_token: Xray Bearer Token
        job_id: submit_tests_bulk 返回的 job_id
        max_polls: 最大轮询次数（默认 30 × 2s = 60s）
        poll_interval: 轮询间隔（秒）
        progress_cb: 回调函数，签名 (poll_count, max_polls, status_msg)
        http_client: 可注入 mock

    Returns:
        创建成功的 Test Case keys 列表

    Raises:
        XrayJobFailedError: Job 执行失败
        XrayJobTimeoutError: 轮询超时
    """
    import requests as _req

    client = http_client or _default_http_client()
    headers = {
        "Authorization": f"Bearer {xray_token}",
        "Content-Type": "application/json",
    }

    for poll_count in range(max_polls):
        time.sleep(poll_interval)

        if progress_cb:
            progress_cb(poll_count + 1, max_polls, f"等待 Xray 处理... ({(poll_count + 1) * poll_interval}s)")

        resp = client.get(
            f"https://xray.cloud.getxray.app/api/v2/import/test/bulk/{job_id}/status",
            headers=headers,
            timeout=15,
        )

        if resp.status_code != 200:
            continue

        status_data = resp.json()
        job_status = status_data.get("status", "").upper()

        if job_status in ["SUCCESSFUL", "COMPLETE", "DONE", "FINISHED"]:
            result_issues = status_data.get("result", {})
            if isinstance(result_issues, dict):
                return [
                    i.get("key")
                    for i in result_issues.get("issues", [])
                    if i.get("key")
                ]
            elif isinstance(result_issues, list):
                return [i.get("key") for i in result_issues if i.get("key")]
            return []

        if job_status in ["FAILED", "ERROR"]:
            raise XrayJobFailedError(f"Xray 导入任务失败: {status_data}")

    raise XrayJobTimeoutError(f"轮询超时（{max_polls * poll_interval}s），Job ID: {job_id}")


class XrayJobFailedError(Exception):
    """Xray Job 执行失败"""


class XrayJobTimeoutError(Exception):
    """Xray Job 轮询超时"""


# ── Step 4a: 查询 Related Ticket 类型 ─────────────────────────────────────

def query_related_ticket(
    base_url: str,
    jira_headers: Dict[str, str],
    ticket_key: str,
    http_client=None,
) -> Tuple[str, str]:
    """
    查询 Jira Ticket 的类型（Test Set / Story 等）和 numeric ID。

    Returns:
        (issue_type_name, numeric_id)  — 如未找到则 ("", "")
    """
    import requests as _req

    client = http_client or _default_http_client()
    resp = client.get(
        f"{base_url}/rest/api/3/issue/{ticket_key.strip().upper()}",
        headers=jira_headers,
        params={"fields": "issuetype,id"},
        timeout=10,
    )

    if resp.status_code != 200:
        return "", ""

    data = resp.json()
    issue_type = (
        data.get("fields", {})
        .get("issuetype", {})
        .get("name", "")
    )
    numeric_id = data.get("id", "")
    return issue_type, numeric_id


# ── Step 4b: 获取 Test Case numeric IDs ───────────────────────────────────

def get_test_numeric_ids(
    base_url: str,
    jira_headers: Dict[str, str],
    test_keys: List[str],
    http_client=None,
) -> List[str]:
    """将 Test Case keys 转换为 numeric IDs（并发，用于 Xray GraphQL）"""
    import requests as _req

    client = http_client or _default_http_client()

    def fetch_one(tc_key: str) -> Optional[str]:
        resp = client.get(
            f"{base_url}/rest/api/3/issue/{tc_key}",
            headers=jira_headers,
            params={"fields": "id"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("id", "")
        return None

    numeric_ids = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_one, k): k for k in test_keys}
        for future in as_completed(futures):
            tc_id = future.result()
            if tc_id:
                numeric_ids.append(tc_id)

    return numeric_ids


# ── Step 4c: 关联到 Test Set ───────────────────────────────────────────────

def link_tests_to_test_set(
    xray_token: str,
    test_set_numeric_id: str,
    test_numeric_ids: List[str],
    http_client=None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    通过 Xray GraphQL 将 Test Cases 添加到 Test Set。

    Returns:
        (success_keys, failure_list)
    """
    import requests as _req

    client = http_client or _default_http_client()
    headers = {
        "Authorization": f"Bearer {xray_token}",
        "Content-Type": "application/json",
    }

    gql_mutation = """
    mutation addTests($testSetId: String!, $testIds: [String!]!) {
      addTestsToTestSet(issueId: $testSetId, testIssueIds: $testIds) {
        addedTests
        warning
      }
    }
    """

    resp = client.post(
        "https://xray.cloud.getxray.app/api/v2/graphql",
        headers=headers,
        json={
            "query": gql_mutation,
            "variables": {
                "testSetId": test_set_numeric_id,
                "testIds": test_numeric_ids,
            },
        },
        timeout=30,
    )

    if resp.status_code != 200:
        return [], [{"key": k, "error": f"GraphQL 请求失败 ({resp.status_code}): {resp.text[:200]}"}
                    for k in test_numeric_ids]

    gql_data = resp.json()
    gql_errors = gql_data.get("errors")

    if gql_errors:
        return [], [{"key": k, "error": str(gql_errors)} for k in test_numeric_ids]

    added = (
        gql_data.get("data", {})
        .get("addTestsToTestSet", {})
        .get("addedTests", [])
    )
    warning = (
        gql_data.get("data", {})
        .get("addTestsToTestSet", {})
        .get("warning", "")
    )
    return test_numeric_ids, []


# ── Step 4d: 关联到 Story（issueLink）──────────────────────────────────────

def link_tests_to_story(
    base_url: str,
    jira_headers: Dict[str, str],
    test_keys: List[str],
    story_ticket: str,
    http_client=None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    通过 Jira issueLink 将 Test Cases 关联到 Story（并发，is tested by）。

    Returns:
        (success_keys, failure_list)
    """
    import requests as _req

    client = http_client or _default_http_client()
    story_key = story_ticket.strip().upper()

    def post_link(test_key: str) -> Tuple[str, bool, Optional[str]]:
        link_payload = {
            "type": {"name": "Test"},
            "inwardIssue": {"key": test_key},
            "outwardIssue": {"key": story_key},
        }
        resp = client.post(
            f"{base_url}/rest/api/3/issueLink",
            headers=jira_headers,
            json=link_payload,
            timeout=10,
        )
        if resp.status_code in [200, 201]:
            return test_key, True, None
        return test_key, False, f"状态码 {resp.status_code}: {resp.text[:150]}"

    success_keys = []
    failures = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(post_link, k): k for k in test_keys}
        for future in as_completed(futures):
            key, ok, err = future.result()
            if ok:
                success_keys.append(key)
            else:
                failures.append({"key": key, "error": err})

    return success_keys, failures

import streamlit as st
import sys
import time
import threading
import queue
import logging
import requests
from datetime import datetime, timezone, timedelta
from requests.auth import HTTPBasicAuth  # type annotation only
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, List, Callable

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.user_config_loader import get_jenkins_config, get_user_config_loader, build_jenkins_auth

st.set_page_config(
    page_title="Jenkins 部署",
    page_icon="🔧",
    layout="wide"
)

FIXED_SERVICES = ["pp-public-api", "pp-psi-service"]

# 生产环境服务列表（Prod 文件夹）
PROD_SERVICES = [
    "prod-public-api",
    "prod-public-api-job",
    "prod-psi-service",
    "prod-psi-web",
]
PROD_BRANCH = "master"

# 生产部署解锁口令（当前阶段固定为 None，永不解锁）
PROD_DEPLOY_ENABLED = False

JENKINS_URL_DEFAULT = "https://jenkins.qima.com"

# ── 检查用户 ──────────────────────────────────────────────────────
if "current_user" not in st.session_state or not st.session_state.current_user:
    st.error("❌ 未选择使用者，请返回主页选择你的身份")
    st.stop()

current_user = st.session_state.current_user
user_jenkins_cfg = get_jenkins_config(current_user)

# ── Session State 初始化 ──────────────────────────────────────────
defaults = {
    "jenkins_logs": [],
    "jenkins_deploying": False,
    "jenkins_results": {},
    "jenkins_done": False,
    "jenkins_deploy_mode": "sequential",
    "jenkins_services_branches": {},
    "jenkins_username_input": user_jenkins_cfg.get("username", "") if user_jenkins_cfg else "",
    "jenkins_token_input": user_jenkins_cfg.get("api_token", "") if user_jenkins_cfg else "",
    "jenkins_url_saved": user_jenkins_cfg.get("jenkins_url", JENKINS_URL_DEFAULT) if user_jenkins_cfg else JENKINS_URL_DEFAULT,
    "jenkins_test_logs": [],
    "jenkins_test_running": False,
    # Prod tab 专用
    "prod_inspect_logs": [],
    "prod_inspect_running": False,
    "prod_unlock_input": "",
    # PP 查询最新分支
    "pp_branch_options": {},
    "pp_branch_fetching": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── 核心 API 工具 ─────────────────────────────────────────────────
def buildJobUrl(service: str, jenkins_url: str, folder: str = "PP") -> str:
    """构建 Jenkins job URL"""
    return f"{jenkins_url.rstrip('/')}/job/{folder}/job/{service}"


def triggerBuild(service: str, branch: str, auth: HTTPBasicAuth,
                 jenkins_url: str, folder: str = "PP") -> Optional[str]:
    """触发构建，返回队列 URL"""
    url = f"{buildJobUrl(service, jenkins_url, folder)}/buildWithParameters"
    try:
        resp = requests.post(url, auth=auth, params={"BRANCH": branch}, timeout=30)
        if resp.status_code in (200, 201):
            return resp.headers.get("Location")
        return None
    except Exception as e:
        logging.warning(f"[Jenkins] triggerBuild failed for {service}: {e}")
        return None


def getBuildNumber(queue_url: str, auth: HTTPBasicAuth,
                   timeout: int = 90) -> Optional[int]:
    """从队列 URL 获取构建编号"""
    api_url = f"{queue_url}api/json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(api_url, auth=auth, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("executable"):
                    return data["executable"]["number"]
        except Exception as e:
            logging.warning(f"[Jenkins] getBuildNumber polling error: {e}")
        time.sleep(3)
    return None


_CONSOLE_KEYWORDS = (
    "error", "exception", "failed", "failure", "fatal",
    "warning", "warn",
    "build", "deploy", "step", "stage",
    "success", "successfully", "finished",
    "started", "running", "pushing", "pulling",
    "docker", "kubectl", "helm",
)

_CONSOLE_NOISE_PREFIXES = (
    "downloading", "progress", "transferring",
    "send request", "receive response",
    "[debug]", "[trace]",
)


def isKeyConsoleLine(line: str) -> bool:
    """判断是否为需要展示的关键日志行"""
    lower = line.lower().strip()
    if not lower:
        return False
    for prefix in _CONSOLE_NOISE_PREFIXES:
        if lower.startswith(prefix):
            return False
    for kw in _CONSOLE_KEYWORDS:
        if kw in lower:
            return True
    return False


def waitForBuild(service: str, build_number: int, auth: HTTPBasicAuth,
                 jenkins_url: str, log_cb: Callable[[str], None],
                 folder: str = "PP", build_timeout: int = 1800) -> bool:
    """轮询等待构建完成，通过 log_cb 回调输出日志（只输出关键行）"""
    job_url = buildJobUrl(service, jenkins_url, folder)
    build_url = f"{job_url}/{build_number}/api/json"
    console_url = f"{job_url}/{build_number}/consoleText"
    start = time.time()
    interval = 15
    last_console_len = 0
    last_progress_log = 0

    while time.time() - start < build_timeout:
        try:
            resp = requests.get(build_url, auth=auth, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                building = data.get("building", False)
                result = data.get("result")

                try:
                    cr = requests.get(console_url, auth=auth, timeout=10)
                    if cr.status_code == 200:
                        full_text = cr.text
                        new_text = full_text[last_console_len:]
                        last_console_len = len(full_text)
                        for line in new_text.splitlines():
                            if isKeyConsoleLine(line):
                                log_cb(f"  │ {line.strip()}")
                except Exception as e:
                    logging.debug(f"[Jenkins] console fetch error (non-fatal): {e}")

                if not building:
                    return result == "SUCCESS"

                now = time.time()
                if now - last_progress_log >= 30:
                    elapsed = int(now - start)
                    log_cb(f"⏳ [{service}] 构建进行中… 已耗时 {elapsed // 60}m{elapsed % 60}s")
                    last_progress_log = now
        except Exception as e:
            log_cb(f"⚠️ [{service}] 查询状态异常: {e}")

        time.sleep(interval)

    log_cb(f"⏱️ [{service}] 构建监控超时")
    return False


def executeDeploy(service: str, branch: str, auth: HTTPBasicAuth,
                  jenkins_url: str, log_cb: Callable[[str], None],
                  folder: str = "PP") -> bool:
    """执行单服务完整部署流程"""
    log_cb(f"🚀 [{service}] 触发构建 (分支: {branch})")
    queue_url = triggerBuild(service, branch, auth, jenkins_url, folder)
    if not queue_url:
        log_cb(f"❌ [{service}] 触发失败，请检查认证信息和服务名称")
        return False

    log_cb(f"📋 [{service}] 已加入队列，等待分配构建编号…")
    build_number = getBuildNumber(queue_url, auth)
    if not build_number:
        log_cb(f"❌ [{service}] 无法获取构建编号，队列超时")
        return False

    build_link = f"{buildJobUrl(service, jenkins_url, folder)}/{build_number}"
    log_cb(f"🔗 [{service}] 构建 #{build_number} 已启动: {build_link}")
    success = waitForBuild(service, build_number, auth, jenkins_url, log_cb, folder)

    if success:
        log_cb(f"✅ [{service}] 构建 #{build_number} 成功！")
    else:
        log_cb(f"❌ [{service}] 构建 #{build_number} 失败")
    return success


# ── 查询最近成功构建分支 ──────────────────────────────────────────
def fetchRecentBranches(service: str, auth: HTTPBasicAuth,
                        jenkins_url: str, folder: str = "PP",
                        max_count: int = 5) -> List[dict]:
    """查询最近成功构建列表，返回 [{"label": ..., "branch": ...}, ...]"""
    base = jenkins_url.rstrip("/")
    tree = "builds[number,result,displayName,timestamp,actions[parameters[name,value]]]{0,20}"
    url = f"{base}/job/{folder}/job/{service}/api/json?tree={tree}"
    tz_cst = timezone(timedelta(hours=8))
    try:
        resp = requests.get(url, auth=auth, timeout=15)
        if resp.status_code != 200:
            return []
        builds = resp.json().get("builds", [])
    except Exception:
        return []

    results = []
    for build in builds:
        if build.get("result") != "SUCCESS":
            continue

        number = build.get("number", "?")
        display_name = build.get("displayName", f"#{number}")
        ts = build.get("timestamp", 0)

        branch = ""
        for action in build.get("actions", []):
            for param in action.get("parameters", []):
                if param.get("name") == "BRANCH":
                    branch = param.get("value", "")
                    break
            if branch:
                break

        if ts:
            dt = datetime.fromtimestamp(ts / 1000, tz=tz_cst)
            time_str = dt.strftime("%b %d, %Y, %I:%M %p")
        else:
            time_str = "N/A"

        label = f"#{number}  {branch or display_name}  ({time_str})"
        results.append({"label": label, "branch": branch or "", "number": number})

        if len(results) >= max_count:
            break

    return results


# ── 后台部署线程 ──────────────────────────────────────────────────
def runDeployThread(services_branches: Dict[str, str], auth: HTTPBasicAuth,
                    jenkins_url: str, is_concurrent: bool,
                    log_q: "queue.Queue", folder: str = "PP"):
    """后台部署线程入口"""
    total = len(services_branches)
    mode = "并发" if is_concurrent else "顺序"
    log_q.put(f"═══ {mode}部署开始，共 {total} 个服务 ═══\n")

    results: Dict[str, bool] = {}

    if is_concurrent:
        def deploy_one(svc: str, br: str):
            return svc, executeDeploy(svc, br, auth, jenkins_url,
                                      log_cb=lambda m: log_q.put(m),
                                      folder=folder)

        with ThreadPoolExecutor(max_workers=total) as executor:
            futures = {
                executor.submit(deploy_one, svc, br): svc
                for svc, br in services_branches.items()
            }
            for future in as_completed(futures):
                try:
                    svc, ok = future.result()
                    results[svc] = ok
                except Exception as e:
                    svc = futures[future]
                    log_q.put(f"❌ [{svc}] 异常: {e}")
                    results[svc] = False
    else:
        for idx, (svc, br) in enumerate(services_branches.items(), 1):
            log_q.put(f"\n▶ [{idx}/{total}] 开始部署 {svc}")
            results[svc] = executeDeploy(svc, br, auth, jenkins_url,
                                         log_cb=lambda m: log_q.put(m),
                                         folder=folder)

    ok = sum(1 for v in results.values() if v)
    log_q.put(f"\n═══ {mode}部署完成: {ok}/{total} 成功 ═══")
    log_q.put(("__DONE__", results))


# ── 连接测试 ──────────────────────────────────────────────────────
def runConnectionTest(username: str, api_token: str, jenkins_url: str,
                      log_q: "queue.Queue"):
    """后台测试 Jenkins 连接（PP 环境）"""
    auth = build_jenkins_auth(username, api_token)
    base = jenkins_url.rstrip("/")

    def put(msg: str):
        log_q.put(msg)

    put("══════════════════════════════════")
    put("  Jenkins API 连接测试")
    put("══════════════════════════════════")
    put(f"  URL   : {base}")
    put(f"  用户  : {username}")
    put(f"  Token : {'*' * 10}{api_token[-4:] if len(api_token) >= 4 else '****'}")
    put("")

    put("【测试 1】验证凭证有效性（/me/api/json）…")
    auth_ok = False
    try:
        r = requests.get(f"{base}/me/api/json", auth=auth, timeout=10)
        if r.status_code == 200:
            d = r.json()
            put(f"  ✅ 成功  Full Name: {d.get('fullName', 'N/A')}")
            put(f"         User ID  : {d.get('id', 'N/A')}")
            auth_ok = True
        elif r.status_code in (401, 403):
            # /me 不可用时，回退用根 API 做凭证探测
            put(f"  ⚠️ /me 返回 {r.status_code}，尝试根 API 验证…")
            r2 = requests.get(f"{base}/api/json", auth=auth, timeout=10)
            if r2.status_code == 200:
                put(f"  ✅ 根 API 可访问，凭证有效")
                auth_ok = True
            else:
                put(f"  ❌ 凭证无效  状态码: {r2.status_code}")
                put(f"         响应: {r2.text[:300]}")
                put("══════════════════════════════════")
                log_q.put(("__TEST_DONE__", False))
                return
        else:
            put(f"  ❌ 失败  状态码: {r.status_code}")
            put(f"         响应: {r.text[:300]}")
            put("══════════════════════════════════")
            log_q.put(("__TEST_DONE__", False))
            return
    except Exception as e:
        put(f"  ❌ 异常: {e}")
        log_q.put(("__TEST_DONE__", False))
        return

    put("")
    put("【测试 2】获取 PP 文件夹任务列表…")
    try:
        r = requests.get(f"{base}/job/PP/api/json", auth=auth, timeout=10)
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            put(f"  ✅ 成功  共 {len(jobs)} 个任务")
            for j in jobs[:5]:
                put(f"         - {j['name']}")
            if len(jobs) > 5:
                put(f"         … 还有 {len(jobs) - 5} 个")
        else:
            put(f"  ❌ 失败  状态码: {r.status_code}")
    except Exception as e:
        put(f"  ❌ 异常: {e}")

    put("")
    put("【测试 3】访问 pp-public-api 任务详情…")
    try:
        r = requests.get(f"{base}/job/PP/job/pp-public-api/api/json", auth=auth, timeout=10)
        if r.status_code == 200:
            d = r.json()
            put(f"  ✅ 成功  任务: {d.get('name', 'N/A')}")
            put(f"         可构建: {d.get('buildable', False)}")
            lb = d.get("lastBuild")
            if lb:
                put(f"         最近构建: #{lb.get('number', 'N/A')}")
        else:
            put(f"  ⚠️ 状态码: {r.status_code}（可能权限不足）")
    except Exception as e:
        put(f"  ❌ 异常: {e}")

    put("")
    put("══════════════════════════════════")
    put("  ✅ 连接测试完成，认证有效")
    put("══════════════════════════════════")
    log_q.put(("__TEST_DONE__", True))


# ── 生产环境服务巡检（只读，不触发构建） ─────────────────────────
def runProdInspect(username: str, api_token: str, jenkins_url: str,
                   log_q: "queue.Queue"):
    """只读查询生产服务状态，绝不触发构建"""
    auth = build_jenkins_auth(username, api_token)
    base = jenkins_url.rstrip("/")

    def put(msg: str):
        log_q.put(msg)

    put("══════════════════════════════════════════")
    put("  🔍 生产服务巡检（只读模式）")
    put("══════════════════════════════════════════")
    put(f"  Jenkins : {base}")
    put(f"  服务数量: {len(PROD_SERVICES)} 个")
    put("")

    # 先尝试获取 Prod 文件夹列表
    put("【步骤 1】探测 Prod 文件夹结构…")
    try:
        r = requests.get(f"{base}/job/Prod/api/json", auth=auth, timeout=10)
        if r.status_code == 200:
            folder_jobs = r.json().get("jobs", [])
            put(f"  ✅ Prod 文件夹存在，共 {len(folder_jobs)} 个任务")
            folder_names = [j["name"] for j in folder_jobs]
            # 检查目标服务是否存在于 Prod 文件夹
            for svc in PROD_SERVICES:
                found = svc in folder_names
                status = "✅ 存在" if found else "⚠️  未找到"
                put(f"     {status} : {svc}")
        elif r.status_code == 404:
            put("  ⚠️  Prod 文件夹不存在或路径不同，将逐个直接查询服务")
        else:
            put(f"  ❌ 查询失败  状态码: {r.status_code}")
    except Exception as e:
        put(f"  ❌ 异常: {e}")

    put("")
    put("【步骤 2】逐一查询各服务详情（Prod 路径）…")

    for svc in PROD_SERVICES:
        put(f"\n  ▷ {svc}")
        # 尝试 /job/Prod/job/<svc>
        url = f"{base}/job/Prod/job/{svc}/api/json"
        try:
            r = requests.get(url, auth=auth, timeout=10)
            if r.status_code == 200:
                d = r.json()
                buildable = d.get("buildable", False)
                desc = d.get("description") or "（无描述）"
                lb = d.get("lastBuild")
                ls = d.get("lastSuccessfulBuild")
                lf = d.get("lastFailedBuild")
                put(f"    ✅ 可访问  可构建: {buildable}")
                put(f"    描述      : {desc[:80]}")
                if lb:
                    put(f"    最近构建  : #{lb.get('number', 'N/A')}")
                if ls:
                    put(f"    最近成功  : #{ls.get('number', 'N/A')}")
                if lf:
                    put(f"    最近失败  : #{lf.get('number', 'N/A')}")
            elif r.status_code == 404:
                put(f"    ⚠️  /job/Prod/job/{svc} 不存在，尝试顶层路径…")
                # fallback：直接 /job/<svc>
                r2 = requests.get(f"{base}/job/{svc}/api/json", auth=auth, timeout=10)
                if r2.status_code == 200:
                    d2 = r2.json()
                    put(f"    ✅ 顶层路径可访问  可构建: {d2.get('buildable', False)}")
                    lb2 = d2.get("lastBuild")
                    if lb2:
                        put(f"    最近构建: #{lb2.get('number', 'N/A')}")
                else:
                    put(f"    ❌ 顶层路径也不存在  状态码: {r2.status_code}")
            else:
                put(f"    ❌ 状态码: {r.status_code}")
                put(f"    响应: {r.text[:200]}")
        except Exception as e:
            put(f"    ❌ 异常: {e}")

    put("")
    put("══════════════════════════════════════════")
    put("  ✅ 巡检完成（未触发任何构建）")
    put("══════════════════════════════════════════")
    log_q.put(("__INSPECT_DONE__", None))


# ── 全局队列（跨 rerun 共享） ─────────────────────────────────────
if "jenkins_log_queue" not in st.session_state:
    st.session_state.jenkins_log_queue = queue.Queue()
if "jenkins_test_queue" not in st.session_state:
    st.session_state.jenkins_test_queue = queue.Queue()
if "prod_inspect_queue" not in st.session_state:
    st.session_state.prod_inspect_queue = queue.Queue()

deploy_q: queue.Queue = st.session_state.jenkins_log_queue
test_q: queue.Queue = st.session_state.jenkins_test_queue
inspect_q: queue.Queue = st.session_state.prod_inspect_queue


# ── UI 渲染 ──────────────────────────────────────────────────────
user_display = get_user_config_loader().get_user_display_name(current_user)
st.title("🔧 Jenkins 部署工具")
st.info(f"👤 当前使用者: **{user_display}** ({current_user})")
st.markdown("---")

# ── 侧边栏 ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Jenkins 认证")

    jenkins_url_val = st.text_input(
        "Jenkins URL",
        value=st.session_state.jenkins_url_saved,
        key="jenkins_url_input"
    )
    jenkins_user_val = st.text_input(
        "用户名 (Azure AD Object ID)",
        value=st.session_state.jenkins_username_input,
        key="jenkins_user_field"
    )
    jenkins_token_val = st.text_input(
        "API Token",
        type="password",
        value=st.session_state.jenkins_token_input,
        key="jenkins_token_field"
    )

    st.session_state.jenkins_url_saved = jenkins_url_val
    st.session_state.jenkins_username_input = jenkins_user_val
    st.session_state.jenkins_token_input = jenkins_token_val

    st.markdown("---")

    # ── 连接测试区 ────────────────────────────────────────────
    st.subheader("🔌 连接测试")
    test_btn = st.button(
        "🔍 测试 Jenkins 连接",
        use_container_width=True,
        disabled=st.session_state.jenkins_test_running,
        key="test_conn_btn"
    )

    if test_btn:
        if not jenkins_user_val or not jenkins_token_val:
            st.error("请先填写用户名和 Token")
        else:
            st.session_state.jenkins_test_logs = []
            while not test_q.empty():
                try:
                    test_q.get_nowait()
                except Exception:
                    break
            st.session_state.jenkins_test_running = True
            threading.Thread(
                target=runConnectionTest,
                args=(jenkins_user_val, jenkins_token_val, jenkins_url_val, test_q),
                daemon=True
            ).start()
            st.rerun()

    if st.session_state.jenkins_test_running or st.session_state.jenkins_test_logs:
        while not test_q.empty():
            try:
                item = test_q.get_nowait()
                if isinstance(item, tuple) and item[0] == "__TEST_DONE__":
                    st.session_state.jenkins_test_running = False
                else:
                    st.session_state.jenkins_test_logs.append(str(item))
            except Exception:
                break

        if st.session_state.jenkins_test_running:
            st.info("⏳ 测试中…")
            time.sleep(0.8)
            st.rerun()

        if st.session_state.jenkins_test_logs:
            st.code("\n".join(st.session_state.jenkins_test_logs), language=None)

    st.markdown("---")

    if st.session_state.jenkins_deploying:
        st.warning("⏳ 部署进行中…")
    elif st.session_state.jenkins_results:
        st.subheader("📊 上次部署结果")
        for svc, ok in st.session_state.jenkins_results.items():
            if ok:
                st.success(f"✅ {svc}")
            else:
                st.error(f"❌ {svc}")


# ── 主体 Tab ─────────────────────────────────────────────────────
prod_tab_label = "🏭 生产环境部署" if PROD_DEPLOY_ENABLED else "🏭 生产环境（调试）"
tab_pp, tab_prod = st.tabs(["🔧 PP 环境部署", prod_tab_label])


# ════════════════════════════════════════════════════════════════
# Tab 1：PP 环境部署
# ════════════════════════════════════════════════════════════════
with tab_pp:
    st.subheader("🎯 PP 环境部署配置")
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("**填写各服务的分支号（留空则跳过该服务）**")

        # ── 服务分支输入区（form 外，支持"查最新"按钮） ────────────
        for svc in FIXED_SERVICES:
            svc_col_input, svc_col_btn = st.columns([4, 1])
            with svc_col_input:
                st.text_input(
                    f"🔹 {svc}",
                    placeholder="例如: release-1.2.248 或 SP-30520",
                    key=f"branch_{svc}"
                )
            with svc_col_btn:
                st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
                fetch_clicked = st.button(
                    "查最新",
                    key=f"fetch_btn_{svc}",
                    use_container_width=True,
                    help=f"查询 {svc} 最近 5 次成功构建的分支"
                )

            if fetch_clicked:
                if not jenkins_user_val or not jenkins_token_val:
                    st.warning(f"⚠️ 请先在侧边栏填写认证信息")
                else:
                    st.session_state.pp_branch_fetching[svc] = True
                    auth_tmp = build_jenkins_auth(jenkins_user_val, jenkins_token_val)
                    options = fetchRecentBranches(svc, auth_tmp, jenkins_url_val, "PP")
                    st.session_state.pp_branch_options[svc] = options
                    st.session_state.pp_branch_fetching[svc] = False
                    st.rerun()

            options_for_svc = st.session_state.pp_branch_options.get(svc, [])
            if st.session_state.pp_branch_fetching.get(svc):
                st.caption(f"⏳ 查询中…")
            elif options_for_svc:
                labels = [o["label"] for o in options_for_svc]

                def onSelectBranch(svc_name: str = svc, opts: List[dict] = options_for_svc):
                    """将下拉选择的分支名写入对应的 text_input"""
                    sel_label = st.session_state.get(f"select_{svc_name}")
                    if sel_label:
                        matched = next((o for o in opts if o["label"] == sel_label), None)
                        if matched and matched["branch"]:
                            st.session_state[f"branch_{svc_name}"] = matched["branch"]

                st.selectbox(
                    f"选择分支（点击后自动填入上方输入框）",
                    options=[""] + labels,
                    key=f"select_{svc}",
                    on_change=onSelectBranch,
                    label_visibility="collapsed"
                )
            elif f"fetch_btn_{svc}" in st.session_state:
                pass

        st.markdown("---")

        # ── 部署模式 + 提交按钮（保留在 form 内） ───────────────────
        with st.form("jenkins_deploy_form"):
            deploy_mode = st.radio(
                "部署模式",
                ["🔁 顺序部署（一个接一个）", "⚡ 并发部署（同时触发）"],
                help="顺序部署：前一个成功后再触发下一个；并发部署：所有服务同时触发"
            )

            submitted = st.form_submit_button(
                "🚀 开始部署",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.jenkins_deploying
            )

    with col_right:
        st.markdown("**服务说明**")
        st.info(
            "🔹 **pp-public-api**\n"
            "Public API 服务，即将迁移至 EKS\n\n"
            "🔹 **pp-psi-service**\n"
            "PSI 服务，即将迁移至 EKS"
        )
        with st.expander("部署模式说明", expanded=True):
            st.markdown(
                "**🔁 顺序部署**\n"
                "- 按顺序逐一部署，前一个完成才触发下一个\n"
                "- 适合有依赖关系的服务\n\n"
                "**⚡ 并发部署**\n"
                "- 所有服务同时触发，互不等待\n"
                "- 适合相互独立的服务，速度更快"
            )

    # 处理 PP 表单提交
    if submitted:
        if not jenkins_user_val or not jenkins_token_val:
            st.error("❌ 请在侧边栏填写 Jenkins 用户名和 API Token")
        else:
            services_to_deploy = {
                svc: st.session_state.get(f"branch_{svc}", "").strip()
                for svc in FIXED_SERVICES
                if st.session_state.get(f"branch_{svc}", "").strip()
            }

            if not services_to_deploy:
                st.warning("⚠️ 请至少为一个服务填写分支号")
            else:
                while not deploy_q.empty():
                    try:
                        deploy_q.get_nowait()
                    except Exception:
                        break
                st.session_state.jenkins_logs = []
                st.session_state.jenkins_results = {}
                st.session_state.jenkins_done = False
                st.session_state.jenkins_deploying = True
                st.session_state.jenkins_deploy_mode = (
                    "concurrent" if "并发" in deploy_mode else "sequential"
                )
                st.session_state.jenkins_services_branches = services_to_deploy

                auth = build_jenkins_auth(jenkins_user_val, jenkins_token_val)
                threading.Thread(
                    target=runDeployThread,
                    args=(services_to_deploy, auth, jenkins_url_val,
                          "并发" in deploy_mode, deploy_q, "PP"),
                    daemon=True
                ).start()
                st.rerun()

    # PP 部署日志区域
    if st.session_state.jenkins_deploying or st.session_state.jenkins_logs:
        st.markdown("---")

        mode_label = (
            "⚡ 并发" if st.session_state.jenkins_deploy_mode == "concurrent"
            else "🔁 顺序"
        )
        svcs = list(st.session_state.jenkins_services_branches.keys())

        while not deploy_q.empty():
            try:
                item = deploy_q.get_nowait()
                if isinstance(item, tuple) and item[0] == "__DONE__":
                    st.session_state.jenkins_results = item[1]
                    st.session_state.jenkins_deploying = False
                    st.session_state.jenkins_done = True
                else:
                    st.session_state.jenkins_logs.append(str(item))
            except Exception:
                break

        if st.session_state.jenkins_deploying:
            st.info(f"⏳ {mode_label} 部署进行中 — {', '.join(svcs)}")
            log_summary = [
                l for l in st.session_state.jenkins_logs
                if any(k in l for k in ("✅", "❌", "🚀", "🔗", "📋", "⏳", "⚠️", "═══", "▶"))
            ]
            if log_summary:
                with st.expander("📋 部署摘要（展开查看详情）", expanded=True):
                    st.code("\n".join(log_summary[-30:]), language=None)
            with st.expander("📜 完整日志", expanded=False):
                st.code("\n".join(st.session_state.jenkins_logs[-200:]), language=None)
            time.sleep(1)
            st.rerun()
        else:
            results = st.session_state.jenkins_results
            ok_count = sum(1 for v in results.values() if v)
            total_count = len(results)

            if ok_count == total_count:
                st.success(f"🎉 全部完成！{ok_count}/{total_count} 个服务部署成功")
            elif ok_count > 0:
                st.warning(f"⚠️ 部分完成：{ok_count}/{total_count} 个服务成功")
            else:
                st.error(f"❌ 全部失败：0/{total_count} 个服务成功")

            c1, c2 = st.columns(2)
            for i, (svc, ok) in enumerate(results.items()):
                col = c1 if i % 2 == 0 else c2
                with col:
                    if ok:
                        st.success(f"✅ **{svc}** 部署成功")
                    else:
                        st.error(f"❌ **{svc}** 部署失败")

            with st.expander("📜 完整部署日志", expanded=False):
                st.code("\n".join(st.session_state.jenkins_logs), language=None)


# ════════════════════════════════════════════════════════════════
# Tab 2：生产环境（调试专用，部署功能锁定）
# ════════════════════════════════════════════════════════════════
with tab_prod:
    # 顶部醒目警告
    st.error(
        "🔒 **生产环境 — 部署功能当前已锁定**\n\n"
        "此 Tab 仅供调试：查看服务状态、验证连接权限。\n"
        "**任何部署操作均不可用，防止误操作生产环境。**"
    )

    st.markdown("---")

    # ── 服务列表展示 ──────────────────────────────────────────
    col_info1, col_info2 = st.columns([1, 1])

    with col_info1:
        st.subheader("📋 目标服务")
        for svc in PROD_SERVICES:
            st.markdown(f"🔹 `{svc}`  —  分支: `{PROD_BRANCH}`")

    with col_info2:
        st.subheader("📌 部署规划说明")
        st.info(
            "**部署模式**：并发（4 个服务同时触发）\n\n"
            "**目标分支**：`master`\n\n"
            "**Jenkins 文件夹**：`/job/Prod/`\n\n"
            "**状态**：⏳ 等待迁移完成后开放"
        )

    st.markdown("---")

    # ── 只读巡检区 ────────────────────────────────────────────
    st.subheader("🔍 服务巡检（只读）")
    st.caption("查询 Jenkins 中生产服务的可访问性和最近构建状态，不触发任何构建。")

    inspect_btn = st.button(
        "🔍 开始巡检生产服务",
        use_container_width=False,
        disabled=st.session_state.prod_inspect_running,
        type="secondary",
        key="prod_inspect_btn"
    )

    if inspect_btn:
        if not jenkins_user_val or not jenkins_token_val:
            st.error("❌ 请先在侧边栏填写认证信息")
        else:
            st.session_state.prod_inspect_logs = []
            while not inspect_q.empty():
                try:
                    inspect_q.get_nowait()
                except Exception:
                    break
            st.session_state.prod_inspect_running = True
            threading.Thread(
                target=runProdInspect,
                args=(jenkins_user_val, jenkins_token_val, jenkins_url_val, inspect_q),
                daemon=True
            ).start()
            st.rerun()

    # 消费巡检队列
    if st.session_state.prod_inspect_running or st.session_state.prod_inspect_logs:
        while not inspect_q.empty():
            try:
                item = inspect_q.get_nowait()
                if isinstance(item, tuple) and item[0] == "__INSPECT_DONE__":
                    st.session_state.prod_inspect_running = False
                else:
                    st.session_state.prod_inspect_logs.append(str(item))
            except Exception:
                break

        if st.session_state.prod_inspect_running:
            st.info("⏳ 巡检中，请稍候…")
            time.sleep(0.8)
            st.rerun()

        if st.session_state.prod_inspect_logs:
            st.code(
                "\n".join(st.session_state.prod_inspect_logs),
                language=None
            )

    st.markdown("---")

    # ── 部署区域 ──────────────────────────────────────────────
    if not PROD_DEPLOY_ENABLED:
        st.subheader("🚀 一键并发部署（锁定中）")
        st.warning(
            "⚠️ 生产部署功能目前处于**锁定状态**，待生产迁移计划确认后由管理员开放。\n\n"
            "开放后将支持：4 个服务并发触发 `master` 分支，实时日志展示。"
        )
        st.button(
            "🔒 生产部署（当前不可用）",
            disabled=True,
            use_container_width=True,
            type="primary",
            key="prod_deploy_locked_btn"
        )
        st.caption("如需开放生产部署，请联系管理员修改 `PROD_DEPLOY_ENABLED = True`。")

    else:
        st.subheader("🚀 一键并发部署 master")
        st.success("✅ 生产部署已开放，将并发触发以下服务的 `master` 分支：")
        for svc in PROD_SERVICES:
            st.markdown(f"  - `{svc}`")

        prod_deploy_btn = st.button(
            "🚀 开始生产并发部署（master）",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("prod_deploying", False),
            key="prod_deploy_btn"
        )

        # 初始化 prod 部署专用 session state
        if "prod_deploying" not in st.session_state:
            st.session_state.prod_deploying = False
        if "prod_deploy_logs" not in st.session_state:
            st.session_state.prod_deploy_logs = []
        if "prod_deploy_results" not in st.session_state:
            st.session_state.prod_deploy_results = {}
        if "prod_deploy_done" not in st.session_state:
            st.session_state.prod_deploy_done = False
        if "prod_deploy_queue" not in st.session_state:
            st.session_state.prod_deploy_queue = queue.Queue()

        prod_deploy_q: queue.Queue = st.session_state.prod_deploy_queue

        if prod_deploy_btn:
            if not jenkins_user_val or not jenkins_token_val:
                st.error("❌ 请在侧边栏填写认证信息")
            else:
                while not prod_deploy_q.empty():
                    try:
                        prod_deploy_q.get_nowait()
                    except Exception:
                        break
                st.session_state.prod_deploy_logs = []
                st.session_state.prod_deploy_results = {}
                st.session_state.prod_deploy_done = False
                st.session_state.prod_deploying = True

                services_branches = {svc: PROD_BRANCH for svc in PROD_SERVICES}
                auth = build_jenkins_auth(jenkins_user_val, jenkins_token_val)
                threading.Thread(
                    target=runDeployThread,
                    args=(services_branches, auth, jenkins_url_val,
                          True, prod_deploy_q, "Prod"),
                    daemon=True
                ).start()
                st.rerun()

        # 生产部署日志区域
        if st.session_state.prod_deploying or st.session_state.prod_deploy_logs:
            st.markdown("---")

            while not prod_deploy_q.empty():
                try:
                    item = prod_deploy_q.get_nowait()
                    if isinstance(item, tuple) and item[0] == "__DONE__":
                        st.session_state.prod_deploy_results = item[1]
                        st.session_state.prod_deploying = False
                        st.session_state.prod_deploy_done = True
                    else:
                        st.session_state.prod_deploy_logs.append(str(item))
                except Exception:
                    break

            if st.session_state.prod_deploying:
                st.info(f"⚡ 并发部署进行中 — {', '.join(PROD_SERVICES)}")
                log_summary = [
                    l for l in st.session_state.prod_deploy_logs
                    if any(k in l for k in ("✅", "❌", "🚀", "🔗", "📋", "⏳", "⚠️", "═══", "▶"))
                ]
                if log_summary:
                    with st.expander("📋 部署摘要（展开查看详情）", expanded=True):
                        st.code("\n".join(log_summary[-30:]), language=None)
                with st.expander("📜 完整日志", expanded=False):
                    st.code("\n".join(st.session_state.prod_deploy_logs[-200:]), language=None)
                time.sleep(1)
                st.rerun()
            else:
                results = st.session_state.prod_deploy_results
                ok_count = sum(1 for v in results.values() if v)
                total_count = len(results)

                if ok_count == total_count:
                    st.success(f"🎉 全部完成！{ok_count}/{total_count} 个服务部署成功")
                elif ok_count > 0:
                    st.warning(f"⚠️ 部分完成：{ok_count}/{total_count} 个服务成功")
                else:
                    st.error(f"❌ 全部失败：0/{total_count} 个服务成功")

                c1, c2 = st.columns(2)
                for i, (svc, ok) in enumerate(results.items()):
                    col = c1 if i % 2 == 0 else c2
                    with col:
                        if ok:
                            st.success(f"✅ **{svc}** 部署成功")
                        else:
                            st.error(f"❌ **{svc}** 部署失败")

                with st.expander("📜 完整部署日志", expanded=False):
                    st.code("\n".join(st.session_state.prod_deploy_logs), language=None)

"""
Test Tools - 测试工具集页面
将测试小工具集成到 Streamlit 界面
"""

import streamlit as st
import sys
import os
import json
import logging
import time
import webbrowser
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules._test_tools._api_perf_test import (
  APIPerformanceTester, TestConfig, parse_curl_command,
)
from modules._test_tools._clean_download import clean_download_files, format_size
from modules._test_tools._create_aca_account import create_aca_account, AccountInfo
from modules._test_tools._create_prefilled_link import PaymentLinkGenerator, DEFAULT_INVOICE_URL
from modules._test_tools._generate_pdf import generate_minimal_pdf
from modules._test_tools._generate_photo import generate_random_photos, generate_number_photos
from modules._test_tools._get_photo_from_url import TESLA_MODEL_MAP, download_tesla_images
from modules._test_tools._python_auto_gui import MouseMover
from modules._test_tools._shein_order import SheinOrderFlow
from modules._test_tools._prod_login_runner import (
  ProdLoginResult,
  ProdLoginRunner,
  casesToRows,
  parseProdLoginCases,
  resolvePlaywrightProjectPath,
)
from modules._myqima_booking._config_builder import LOB_BOOKING_TYPES, EA_VARIANTS, ENVA_VARIANTS

st.set_page_config(page_title="Test Tools", page_icon="🧪", layout="wide")

st.title("🧪 Test Tools")
st.markdown("日常测试辅助工具集合，全部在本地运行。")

# Initialize session_state
if "mouse_mover" not in st.session_state:
  st.session_state.mouse_mover = MouseMover()

if "shein_logs" not in st.session_state:
  st.session_state.shein_logs = []

if "myqima_regression_summary" not in st.session_state:
  st.session_state.myqima_regression_summary = None
if "myqima_regression_running" not in st.session_state:
  st.session_state.myqima_regression_running = False
if "prefilled_last_request_id" not in st.session_state:
  st.session_state.prefilled_last_request_id = ""
if "prefilled_last_env" not in st.session_state:
  st.session_state.prefilled_last_env = "PP"
if "prefilled_last_link_result" not in st.session_state:
  st.session_state.prefilled_last_link_result = None
if "prefilled_last_invoice_result" not in st.session_state:
  st.session_state.prefilled_last_invoice_result = None
if "prod_login_running" not in st.session_state:
  st.session_state.prod_login_running = False
if "prod_login_last_result" not in st.session_state:
  st.session_state.prod_login_last_result = None
if "pr_url_open_result" not in st.session_state:
  st.session_state.pr_url_open_result = None


# ── 0. Prod 快速验证 ──
with st.expander("⚡ Prod 快速验证", expanded=False):
  st.markdown(
    "运行 Playwright `prod-login.spec.ts` 整套生产环境冒烟用例，"
    "实时输出日志与通过/失败汇总。"
  )
  st.caption("运行中请勿刷新页面，否则可能导致浏览器进程残留。")

  _prod_cfg = {}
  _prod_curr_user = st.session_state.get("current_user")
  _prod_cfg_path = os.path.join(
    os.path.dirname(__file__), "..", "config", "users_config.json"
  )
  if _prod_curr_user:
    try:
      with open(_prod_cfg_path, encoding="utf-8") as _fh:
        _prod_all_cfg = json.load(_fh)
      _prod_cfg = (
        _prod_all_cfg.get("users", {})
        .get(_prod_curr_user, {})
        .get("myqima", {})
      )
    except Exception:
      pass

  _webtools_root = Path(__file__).resolve().parents[1]
  _prod_default_path = _prod_cfg.get("playwright_project_path", "") or ""
  try:
    _prod_resolved = resolvePlaywrightProjectPath(
      _prod_default_path, _webtools_root
    )
    _prod_path_value = str(_prod_resolved)
  except FileNotFoundError:
    _prod_path_value = _prod_default_path

  _prod_playwright_path = st.text_input(
    "Playwright 项目路径",
    value=_prod_path_value,
    key="prod_login_playwright_path",
    help="优先使用 users_config 中 myqima.playwright_project_path；"
    "为空时自动探测与 webtools 同级的 playwright 目录",
  )
  _prod_headed = st.checkbox(
    "显示浏览器（headed）",
    value=False,
    key="prod_login_headed",
    help="默认无头运行；勾选后弹出 Chromium 便于目视排查",
  )

  _prod_col_run, _prod_col_clear = st.columns(2)
  with _prod_col_run:
    _btn_prod = st.button(
      "▶️ 开始 Prod 验证",
      use_container_width=True,
      key="btn_prod_login",
      disabled=st.session_state.prod_login_running,
    )
  with _prod_col_clear:
    if st.button(
      "🗑️ 清空结果", use_container_width=True, key="btn_prod_login_clear"
    ):
      st.session_state.prod_login_last_result = None
      st.rerun()

  if _btn_prod:
    if not _prod_playwright_path or not _prod_playwright_path.strip():
      st.error("请配置 Playwright 项目路径")
    else:
      try:
        _prod_proj = resolvePlaywrightProjectPath(
          _prod_playwright_path.strip(), _webtools_root
        )
      except FileNotFoundError as _prod_path_err:
        st.error(str(_prod_path_err))
        _prod_proj = None

      if _prod_proj is not None:
        if _prod_curr_user:
          try:
            with open(_prod_cfg_path, encoding="utf-8") as _fh:
              _prod_all_cfg = json.load(_fh)
            if "users" not in _prod_all_cfg:
              _prod_all_cfg["users"] = {}
            if _prod_curr_user not in _prod_all_cfg["users"]:
              _prod_all_cfg["users"][_prod_curr_user] = {}
            if "myqima" not in _prod_all_cfg["users"][_prod_curr_user]:
              _prod_all_cfg["users"][_prod_curr_user]["myqima"] = {}
            _prod_all_cfg["users"][_prod_curr_user]["myqima"][
              "playwright_project_path"
            ] = str(_prod_proj)
            with open(_prod_cfg_path, "w", encoding="utf-8") as _fh:
              json.dump(_prod_all_cfg, _fh, indent=2, ensure_ascii=False)
          except Exception as _prod_save_ex:
            logging.warning("保存 playwright_project_path 失败: %s", _prod_save_ex)

        st.session_state.prod_login_running = True
        _prod_case_box = st.empty()
        _prod_log_box = st.empty()
        _prod_log_lines: list[str] = []
        _prod_run_result: ProdLoginResult | None = None
        _prod_log_keep = 500
        try:
          _prod_runner = ProdLoginRunner(_prod_proj)
          with st.spinner("正在执行 Prod 快速验证（整套 prod-login）..."):
            for _prod_item in _prod_runner.stream(headed=_prod_headed):
              if isinstance(_prod_item, str):
                _prod_log_lines.append(_prod_item)
                _prod_live_cases = parseProdLoginCases(_prod_log_lines)
                if _prod_live_cases:
                  _prod_case_box.dataframe(
                    casesToRows(_prod_live_cases),
                    use_container_width=True,
                    hide_index=True,
                  )
                if len(_prod_log_lines) % 2 == 0:
                  _prod_log_box.code(
                    "\n".join(_prod_log_lines[-80:]), language="text"
                  )
              else:
                _prod_run_result = _prod_item

          _prod_final_cases = (
            _prod_run_result.cases
            if _prod_run_result and _prod_run_result.cases
            else parseProdLoginCases(_prod_log_lines)
          )
          if _prod_final_cases:
            _prod_case_box.dataframe(
              casesToRows(_prod_final_cases),
              use_container_width=True,
              hide_index=True,
            )
          _prod_log_box.code("\n".join(_prod_log_lines[-120:]), language="text")
          st.session_state.prod_login_last_result = {
            "success": bool(_prod_run_result and _prod_run_result.success),
            "passed": _prod_run_result.passed if _prod_run_result else 0,
            "failed": _prod_run_result.failed if _prod_run_result else 0,
            "skipped": _prod_run_result.skipped if _prod_run_result else 0,
            "exit_code": (
              _prod_run_result.exit_code if _prod_run_result else None
            ),
            "error": _prod_run_result.error if _prod_run_result else "",
            "logs": _prod_log_lines[-_prod_log_keep:],
            "cases": casesToRows(_prod_final_cases),
            "project_path": str(_prod_proj),
            "headed": _prod_headed,
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          }
        except Exception as _prod_ex:
          st.error(f"执行异常: {_prod_ex}")
          _prod_err_cases = parseProdLoginCases(_prod_log_lines)
          st.session_state.prod_login_last_result = {
            "success": False,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "exit_code": None,
            "error": str(_prod_ex),
            "logs": _prod_log_lines[-_prod_log_keep:],
            "cases": casesToRows(_prod_err_cases),
            "project_path": str(_prod_proj),
            "headed": _prod_headed,
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          }
        finally:
          st.session_state.prod_login_running = False
          st.rerun()

  _prod_prev = st.session_state.prod_login_last_result
  if _prod_prev:
    st.markdown("#### 📊 最近一次结果")
    st.caption(
      f"完成时间: {_prod_prev.get('finished_at', '-')} | "
      f"路径: {_prod_prev.get('project_path', '-')} | "
      f"headed: {_prod_prev.get('headed', False)}"
    )
    _pm1, _pm2, _pm3, _pm4 = st.columns(4)
    _pm1.metric("状态", "✅ 通过" if _prod_prev.get("success") else "❌ 失败")
    _pm2.metric("Passed", _prod_prev.get("passed", 0))
    _pm3.metric("Failed", _prod_prev.get("failed", 0))
    _pm4.metric("Skipped", _prod_prev.get("skipped", 0))
    if _prod_prev.get("error") and not _prod_prev.get("success"):
      st.error(_prod_prev["error"])
    _prod_case_rows = _prod_prev.get("cases") or []
    if _prod_case_rows:
      st.markdown("##### 用例明细")
      st.dataframe(
        _prod_case_rows, use_container_width=True, hide_index=True
      )
    with st.expander("📋 完整日志", expanded=False):
      st.code("\n".join(_prod_prev.get("logs") or []), language="text")


# ── 1. API 性能测试 ──
with st.expander("🚀 API 性能测试", expanded=False):
  st.markdown("对目标 API 进行并发压力测试，生成响应时间分布和吞吐量报告。")

  col1, col2 = st.columns(2)
  with col1:
    api_url = st.text_input("API URL", placeholder="https://api.example.com/data")
    api_method = st.selectbox("HTTP Method", ["GET", "POST"])
  with col2:
    concurrent_users = st.number_input("并发用户数", min_value=1, value=10, step=1)
    test_mode_api = st.selectbox("测试模式", ["按请求数", "按持续时间"], key="test_mode_api")
    if test_mode_api == "按请求数":
      total_requests = st.number_input("总请求数", min_value=1, value=100, step=10)
    else:
      duration_seconds = st.number_input("持续时间(秒)", min_value=5, value=60, step=5)

  api_headers = st.text_area("Headers (JSON)", height=80, placeholder='{"Authorization": "Bearer xxx"}')
  api_params = st.text_area("Params (JSON)", height=80, placeholder='{"page": "1", "size": "10"}')

  col1, col2 = st.columns([1, 1])
  with col1:
    api_curl = st.text_area("或直接粘贴 curl 命令", height=100, placeholder="curl --location 'https://...' --header '...'")
  with col2:
    st.markdown("#####  ")
    if st.button("🚀 开始测试", use_container_width=True, key="btn_api_test"):
      if not api_url and not api_curl:
        st.error("请输入 API URL 或 curl 命令")
      else:
        try:
          if api_curl:
            config = parse_curl_command(api_curl)
          else:
            config = TestConfig(
              url=api_url, method=api_method,
              headers=json.loads(api_headers) if api_headers else None,
              params=json.loads(api_params) if api_params else {},
            )
          config.concurrent_users = concurrent_users
          if test_mode_api == "按持续时间":
            config.test_mode = "duration"
            config.duration_seconds = duration_seconds
          else:
            config.total_requests = total_requests
          tester = APIPerformanceTester(config)
          with st.spinner("正在执行测试..."):
            if config.test_mode == "duration":
              results = tester.run_duration_test()
            else:
              results = tester.run_sync_test()
          report = tester.generate_report(results)
          fig = tester.create_charts(results, report)

          st.markdown("### 📊 测试报告")
          m1, m2, m3, m4 = st.columns(4)
          m1.metric("成功率", f"{report.success_rate:.1f}%")
          m2.metric("平均响应时间", f"{report.average_response_time * 1000:.1f}ms")
          m3.metric("P95", f"{report.p95_response_time * 1000:.1f}ms")
          m4.metric("吞吐量", f"{report.requests_per_second:.1f} RPS")

          c1, c2, c3 = st.columns(3)
          c1.metric("成功/总计", f"{report.successful_requests}/{report.total_requests}")
          c2.metric("测试耗时", f"{report.test_duration:.2f}s")
          c3.metric("并发用户", f"{report.concurrent_users}")

          colStat1, colStat2 = st.columns(2)
          with colStat1:
            st.metric("P75", f"{report.p75_response_time * 1000:.1f}ms")
            st.metric("P90", f"{report.p90_response_time * 1000:.1f}ms")
            st.metric("P99", f"{report.p99_response_time * 1000:.1f}ms")
            st.metric("标准差", f"{report.std_dev_response_time * 1000:.2f}ms")
          with colStat2:
            st.metric("数据量", f"{report.total_data_transferred / 1024:.1f}KB")
            st.metric("最小响应", f"{report.min_response_time * 1000:.1f}ms")
            st.metric("最大响应", f"{report.max_response_time * 1000:.1f}ms")
            st.metric("失败数", f"{report.failed_requests}")

          st.pyplot(fig)

          with st.expander("📋 详细报告"):
            scDist = {str(k): v for k, v in sorted((report.status_code_distribution or {}).items())}
            st.json({
              "total_requests": report.total_requests,
              "successful": report.successful_requests,
              "failed": report.failed_requests,
              "success_rate": f"{report.success_rate:.2f}%",
              "avg_ms": round(report.average_response_time * 1000, 2),
              "median_ms": round(report.median_response_time * 1000, 2),
              "p75_ms": round(report.p75_response_time * 1000, 2),
              "p90_ms": round(report.p90_response_time * 1000, 2),
              "p95_ms": round(report.p95_response_time * 1000, 2),
              "p99_ms": round(report.p99_response_time * 1000, 2),
              "std_dev_ms": round(report.std_dev_response_time * 1000, 2),
              "min_ms": round(report.min_response_time * 1000, 2),
              "max_ms": round(report.max_response_time * 1000, 2),
              "rps": round(report.requests_per_second, 2),
              "duration_sec": round(report.test_duration, 2),
              "concurrent_users": report.concurrent_users,
              "data_transferred_kb": round(report.total_data_transferred / 1024, 2),
              "status_code_distribution": scDist,
              "error_distribution": report.error_distribution or {},
            })
        except Exception as e:
          st.error(f"测试失败: {e}")


# ── 2. 下载目录清理 ──
with st.expander("🗑️ 下载目录清理", expanded=False):
  st.markdown("清理指定目录中的特定类型文件。")

  clean_path = st.text_input("目标目录", value=os.path.expanduser("~/Downloads"), key="clean_path")
  clean_exts = st.text_input("文件扩展名（逗号分隔）", value="exe, zip, jpg, png", key="clean_exts")

  if st.button("🔍 扫描并清理", use_container_width=True, key="btn_clean_scan"):
    exts = [e.strip() for e in clean_exts.split(",") if e.strip()]
    result = clean_download_files(clean_path, exts)
    if result["deleted_count"] > 0 or result["failed_count"] > 0:
      st.success(f"已删除 {result['deleted_count']} 个文件（{format_size(result['total_size'])}），失败 {result['failed_count']} 个")
      if result["deleted_files"]:
        with st.expander("已删除文件列表"):
          for f in result["deleted_files"]:
            st.text(f)
      if result["failed_files"]:
        with st.expander("失败详情"):
          for f in result["failed_files"]:
            st.error(f"{f['file']}: {f['error']}")
    else:
      st.info("未找到匹配的文件")


# ── 3. ACA 账号创建 ──
with st.expander("🏢 ACA 账号创建", expanded=False):
  st.markdown("在 DEV/PP 环境快速创建测试公司账号。")

  col1, col2 = st.columns(2)
  with col1:
    aca_login = st.text_input("登录名", key="aca_login")
    aca_email = st.text_input("邮箱", key="aca_email")
  with col2:
    aca_password = st.text_input("密码", type="password", key="aca_password")
    aca_company = st.text_input("公司名称", key="aca_company")
  aca_env = st.selectbox("环境", ["PP", "DEV"], key="aca_env")

  if st.button("创建账号", use_container_width=True, key="btn_aca"):
    if not all([aca_login, aca_email, aca_password, aca_company]):
      st.error("请填写所有必填字段")
    else:
      info = AccountInfo(login=aca_login, emails=aca_email, password=aca_password, company_name=aca_company)
      result = create_aca_account(info, aca_env)
      if result["success"]:
        st.success("✅ 账号创建成功")
        if "account_info" in result:
          st.json(result["account_info"])
        if "data" in result:
          st.json(result["data"])
      else:
        st.error(f"❌ 创建失败: {result.get('error', '未知错误')}")


# ── 4. Prefilled Link 生成 ──
with st.expander("🔗 Prefilled Link 生成", expanded=False):
  st.markdown("生成预填充支付链接（两步流程，自动获取 sign）。")

  link_mode = st.selectbox("模式", ["正常", "随机金额", "分钟精度", "已过期", "待生效"], key="link_mode")

  c1, c2, c3 = st.columns(3)
  with c1:
    link_amount = st.number_input("金额", min_value=0.01, value=250.0, step=10.0, key="link_amount")
  with c2:
    link_env = st.selectbox("环境", ["PP", "DEV", "PROD"], key="link_env")
  with c3:
    link_bu = st.selectbox("BU", ["qima", "qimawqs", "qimacertis", "qimawqsmexico"], key="link_bu")

  c1, c2, c3 = st.columns(3)
  with c1:
    link_currency = st.selectbox("币种", ["USD", "EUR", "MXN"], key="link_currency")
  with c2:
    link_discount_pct = st.number_input("折扣比例", min_value=0.0, max_value=1.0, value=0.05, step=0.01, format="%.2f", key="link_discount_pct")
  with c3:
    link_customer_id = st.text_input("客户ID", value="5C9B1F313EE14F95B79372F950F88165", key="link_customer_id")

  # 根据模式动态展示有效期字段
  link_days_val = 2
  link_minutes_val = 30
  link_pending_val = 10
  link_duration_val = 60

  if link_mode in ("正常", "随机金额"):
    link_days_val = st.number_input("有效期（天）", min_value=0, value=2, key="link_days")
  elif link_mode == "分钟精度":
    link_minutes_val = st.number_input("有效期（分钟）", min_value=1, value=30, key="link_minutes")
  elif link_mode == "已过期":
    link_minutes_val = st.number_input("已过期（分钟）", min_value=1, value=5, key="link_minutes",
                                       help="结束时间在当前时间之前多少分钟")
  elif link_mode == "待生效":
    pc1, pc2 = st.columns(2)
    with pc1:
      link_pending_val = st.number_input("开始前等待（分钟）", min_value=1, value=10, key="link_pending",
                                         help="折扣开始时间在当前时间之后多少分钟")
    with pc2:
      link_duration_val = st.number_input("折扣持续（分钟）", min_value=1, value=60, key="link_duration")

  col1, col2 = st.columns([1, 3])
  with col1:
    if st.button("生成 Link", use_container_width=True, key="btn_link"):
      if not link_amount:
        st.error("请输入金额")
      else:
        try:
          import modules._test_tools._create_prefilled_link as _cpl
          _cpl.DEFAULT_FIELDS["bu"] = link_bu
          _cpl.DEFAULT_FIELDS["currency"] = link_currency
          _cpl.DEFAULT_FIELDS["percentDiscount"] = link_discount_pct
          _cpl.DEFAULT_FIELDS["customerId"] = link_customer_id

          generator = PaymentLinkGenerator(environment=link_env)
          with st.spinner("正在生成..."):
            if link_mode == "随机金额":
              result = generator.generate_random_link(discount_days=link_days_val)
            elif link_mode == "分钟精度":
              result = generator.generate_link_by_minutes(amount=link_amount, discount_minutes=link_minutes_val)
            elif link_mode == "已过期":
              result = generator.generate_expired_link(amount=link_amount, expired_minutes=link_minutes_val)
            elif link_mode == "待生效":
              result = generator.generate_pending_link(amount=link_amount, pending_minutes=link_pending_val, discount_duration_minutes=link_duration_val)
            else:
              result = generator.generate_link(amount=link_amount, discount_days=link_days_val)
          if result.success:
            _rid = ""
            if result.request_data:
              _rid = result.request_data.get("requestId", "") or ""
            if _rid:
              st.session_state.prefilled_last_request_id = _rid
              st.session_state.prefilled_last_env = link_env
              st.session_state.invoice_original_request_id = _rid
              st.session_state.invoice_env = link_env
            st.session_state.prefilled_last_link_result = {
              "success": True,
              "link_url": result.link_url,
              "sign": result.sign,
              "request_id": _rid,
              "request_data": result.request_data,
              "error_message": None,
            }
          else:
            st.session_state.prefilled_last_link_result = {
              "success": False,
              "link_url": None,
              "sign": None,
              "request_id": "",
              "request_data": None,
              "error_message": result.error_message,
            }
        except Exception as e:
          st.session_state.prefilled_last_link_result = {
            "success": False,
            "link_url": None,
            "sign": None,
            "request_id": "",
            "request_data": None,
            "error_message": str(e),
          }

  _last_link = st.session_state.prefilled_last_link_result
  if _last_link:
    if _last_link.get("success"):
      st.success("✅ 生成成功")
      if _last_link.get("link_url"):
        st.code(_last_link["link_url"], language="text")
      else:
        st.info("响应已返回但未包含 linkUrl，可查看下方详细数据")
      if _last_link.get("sign"):
        st.text(f"Sign: {_last_link['sign']}")
      if _last_link.get("request_id"):
        st.text(f"RequestId: {_last_link['request_id']}")
      if _last_link.get("request_data"):
        with st.expander("请求数据", expanded=False):
          st.json(_last_link["request_data"])
    else:
      st.error(f"生成失败: {_last_link.get('error_message')}")

  st.markdown("---")
  st.markdown("##### 📄 推送 Invoice")
  st.caption(
    "两步流程自动获取 sign。"
    "生成 Link 成功后会自动带入 originalRequestId；也可手动填写单独推送。"
  )

  _last_rid = st.session_state.prefilled_last_request_id or ""
  _default_invoice_env = st.session_state.prefilled_last_env or link_env

  inv_c1, inv_c2 = st.columns(2)
  with inv_c1:
    invoice_original_id = st.text_input(
      "originalRequestId",
      value=_last_rid,
      key="invoice_original_request_id",
      help="第一次生成 Link 时的 requestId；生成成功后会自动填入，也可手动修改",
    )
  with inv_c2:
    invoice_env = st.selectbox(
      "推送环境",
      ["PP", "DEV", "PROD"],
      index=["PP", "DEV", "PROD"].index(_default_invoice_env)
      if _default_invoice_env in ("PP", "DEV", "PROD") else 0,
      key="invoice_env",
    )

  invoice_url = st.text_input(
    "附件 URL (invoiceUrl)",
    value=DEFAULT_INVOICE_URL,
    key="invoice_url",
  )

  if _last_rid:
    st.info(f"最近一次生成的 RequestId: `{_last_rid}`（环境: {st.session_state.prefilled_last_env}）")

  inv_btn1, inv_btn2 = st.columns([1, 3])
  with inv_btn1:
    if st.button("推送 Invoice", use_container_width=True, key="btn_push_invoice"):
      if not invoice_original_id or not invoice_original_id.strip():
        st.error("请填写 originalRequestId（可先生成 Link，或手动输入）")
      elif not invoice_url or not invoice_url.strip():
        st.error("请填写附件 URL")
      else:
        try:
          inv_gen = PaymentLinkGenerator(environment=invoice_env)
          with st.spinner("正在推送 Invoice（两步获取 sign）..."):
            inv_result = inv_gen.push_invoice(
              original_request_id=invoice_original_id.strip(),
              invoice_url=invoice_url.strip(),
            )
          st.session_state.prefilled_last_invoice_result = {
            "success": inv_result.success,
            "request_id": inv_result.request_id,
            "original_request_id": inv_result.original_request_id,
            "sign": inv_result.sign,
            "error_message": inv_result.error_message,
            "response_data": inv_result.response_data,
          }
        except Exception as e:
          st.session_state.prefilled_last_invoice_result = {
            "success": False,
            "request_id": None,
            "original_request_id": invoice_original_id.strip(),
            "sign": None,
            "error_message": str(e),
            "response_data": None,
          }

  _last_invoice = st.session_state.prefilled_last_invoice_result
  if _last_invoice:
    if _last_invoice.get("success"):
      st.success("✅ Invoice 推送成功")
      st.text(f"requestId: {_last_invoice.get('request_id')}")
      st.text(f"originalRequestId: {_last_invoice.get('original_request_id')}")
      if _last_invoice.get("sign"):
        st.text(f"Sign: {_last_invoice['sign']}")
      if _last_invoice.get("response_data") is not None:
        with st.expander("响应数据"):
          if isinstance(_last_invoice["response_data"], dict):
            st.json(_last_invoice["response_data"])
          else:
            st.code(str(_last_invoice["response_data"]), language="text")
    else:
      st.error(f"推送失败: {_last_invoice.get('error_message')}")
      if _last_invoice.get("response_data") is not None:
        with st.expander("失败响应"):
          if isinstance(_last_invoice["response_data"], dict):
            st.json(_last_invoice["response_data"])
          else:
            st.code(str(_last_invoice["response_data"]), language="text")


# ── 5. PDF 生成 ──
with st.expander("📄 PDF 文件生成", expanded=False):
  st.markdown("生成指定大小的有效 PDF 文件，用于测试上传/下载功能。")

  col1, col2 = st.columns(2)
  with col1:
    pdf_size = st.number_input("目标大小 (MB)", min_value=1, value=5, key="pdf_size")
  with col2:
    pdf_count = st.number_input("文件数量", min_value=1, value=3, key="pdf_count")

  pdf_output_dir = os.path.join(os.getcwd(), "results", "generated_pdf")
  st.caption(f"保存路径: {pdf_output_dir}")

  if st.button("生成 PDF", use_container_width=True, key="btn_pdf"):
    with st.spinner("正在生成 PDF 文件..."):
      try:
        files = generate_minimal_pdf(target_size_mb=pdf_size, file_count=pdf_count, output_dir=pdf_output_dir)
        st.success(f"✅ 成功生成 {len(files)} 个 PDF 文件")
        for f in files:
          size = os.path.getsize(f) / (1024 * 1024)
          st.text(f"📄 {os.path.basename(f)} — {size:.1f} MB")
          with open(f, "rb") as fh:
            st.download_button(f"⬇️ 下载 {os.path.basename(f)}", data=fh, file_name=os.path.basename(f), key=f"dl_pdf_{os.path.basename(f)}")
      except Exception as e:
        st.error(f"生成失败: {e}")


# ── 6. 图片生成 ──
with st.expander("🖼️ 图片生成", expanded=False):
  st.markdown("生成随机像素图或带数字的测试图片。")

  col1, col2, col3 = st.columns(3)
  with col1:
    photo_type = st.selectbox("类型", ["随机像素", "带数字"], key="photo_type")
  with col2:
    photo_count = st.number_input("数量", min_value=1, value=5, key="photo_count")
  with col3:
    photo_width = st.number_input("宽度", min_value=10, value=200, step=10, key="photo_width")
    photo_height = st.number_input("高度", min_value=10, value=200, step=10, key="photo_height")

  photo_output_dir = os.path.join(os.getcwd(), "results", "generated_photos")
  st.caption(f"保存路径: {photo_output_dir}")

  if st.button("生成图片", use_container_width=True, key="btn_photo"):
    with st.spinner("正在生成图片..."):
      try:
        if photo_type == "随机像素":
          files = generate_random_photos(num_photos=photo_count, width=photo_width, height=photo_height, output_dir=photo_output_dir)
        else:
          files = generate_number_photos(num_photos=photo_count, width=photo_width, height=photo_height, output_dir=photo_output_dir)
        st.success(f"✅ 生成 {len(files)} 张图片")
        cols = st.columns(min(5, len(files)))
        for i, f in enumerate(files):
          if i < 5:
            with cols[i]:
              st.image(f, caption=os.path.basename(f), use_container_width=True)
      except Exception as e:
        st.error(f"生成失败: {e}")


# ── 7. Tesla 图片下载 ──
with st.expander("📸 Tesla 车型图片下载", expanded=False):
  st.markdown("从 Tesla 官方图库下载指定车型图片。")

  col1, col2 = st.columns(2)
  with col1:
    tesla_model = st.selectbox("车型", list(TESLA_MODEL_MAP.keys()), key="tesla_model")
  with col2:
    tesla_count = st.number_input("下载数量", min_value=1, max_value=50, value=10, key="tesla_count")

  tesla_output_dir = os.path.join(os.getcwd(), "results", "tesla_photos")
  st.caption(f"保存路径: {tesla_output_dir}")

  if st.button("下载图片", use_container_width=True, key="btn_tesla"):
    try:
      with st.spinner("正在从 Tesla 下载图片..."):
        files = download_tesla_images(tesla_model, tesla_output_dir, target_count=tesla_count)
      st.success(f"✅ 下载 {len(files)} 张图片")
      cols = st.columns(min(5, len(files)))
      for i, f in enumerate(files):
        if i < 5:
          with cols[i]:
            st.image(f, caption=os.path.basename(f), use_container_width=True)
    except Exception as e:
      st.error(f"下载失败: {e}")


# ── 8. 鼠标自动移动 ──
with st.expander("🖱️ 鼠标自动移动", expanded=False):
  st.markdown("自动随机移动鼠标并点击，防止屏幕保护或模拟操作。")

  mover = st.session_state.mouse_mover
  interval = st.number_input("移动间隔（秒）", min_value=5, value=int(mover.interval), step=5, key="mouse_interval")

  col1, col2, col3 = st.columns([1, 1, 2])
  with col1:
    if st.button("▶️ 启动", use_container_width=True, key="btn_mouse_start"):
      mover.interval = interval
      mover.start()
      st.rerun()
  with col2:
    if st.button("⏹️ 停止", use_container_width=True, key="btn_mouse_stop"):
      mover.stop()
      st.rerun()
  with col3:
    status = "🟢 运行中" if mover.is_running else "🔴 已停止"
    st.markdown(f"### 状态: {status}")


# ── 9. SHEIN 订单测试 ──
with st.expander("📋 SHEIN 订单流程测试", expanded=False):
  st.markdown("模拟 SHEIN 订单请求到 QIMA 的完整流程（串行执行，后一步依赖前一步成功）。")

  col1, col2 = st.columns([1, 2])
  with col1:
    if st.button("▶️ 执行全部步骤", use_container_width=True, key="btn_shein"):
      st.session_state.shein_logs = []
      flow = SheinOrderFlow()
      st.session_state.shein_logs.append(flow.log("开始 SHEIN 订单流程测试"))

      with st.spinner("步骤1: 模拟 SHEIN 发送订单请求..."):
        step1_ok = flow.step1_2_mock_shein_booking_request()
      if step1_ok:
        st.session_state.shein_logs.append(flow.log("✅ 步骤1完成: 订单模拟请求发送成功"))

        with st.spinner("步骤2: 处理订单并创建 LT 订单..."):
          step2_ok = flow.step3_4_process_booking_request()
        if step2_ok:
          st.session_state.shein_logs.append(flow.log(f"✅ 步骤2完成: AIMS订单号 {flow.lt_ref_num}"))
          st.session_state.shein_logs.append(flow.log("🎉 流程全部完成"))
        else:
          st.session_state.shein_logs.append(flow.log("❌ 步骤2失败，流程中断"))
      else:
        st.session_state.shein_logs.append(flow.log("❌ 步骤1失败，流程中断"))
      st.rerun()

    if st.button("🗑️ 清空日志", use_container_width=True, key="btn_shein_clear"):
      st.session_state.shein_logs = []
      st.rerun()

  with col2:
    for log in st.session_state.shein_logs:
      st.text(log)


# ── 10. myQIMA 自动下单 ──
with st.expander("🏪 myQIMA 自动下单", expanded=False):
  st.markdown("通过 Playwright 自动执行 myQIMA 业务线下单流程。")

  # 读取当前用户配置
  _myqima_cfg = {}
  _curr_user = st.session_state.get("current_user")
  if _curr_user:
    _cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "users_config.json")
    try:
      with open(_cfg_path, encoding="utf-8") as _fh:
        _all_cfg = json.load(_fh)
      _myqima_cfg = _all_cfg.get("users", {}).get(_curr_user, {}).get("myqima", {})
    except Exception:
      pass

  _default_direct = _myqima_cfg.get("directAccount", {})
  _default_ppsso = _myqima_cfg.get("ppssoBackdoor", {})
  _default_path = _myqima_cfg.get("playwright_project_path", "")

  # 先声明变量默认值，防止 Streamlit 条件渲染导致 NameError
  _direct_user = ""
  _direct_pwd = ""
  _ppsso_cid_val = ""
  _ppsso_user_val = ""
  _ppsso_pwd_val = ""

  # 登录方式
  _login_method = st.radio(
    "登录方式", ["myQIMA 账号", "PPSO CompanyId"],
    horizontal=True, key="myqima_login_method",
  )

  if _login_method == "myQIMA 账号":
    col1, col2 = st.columns(2)
    with col1:
      _direct_user = st.text_input(
        "myQIMA 账号", value=_default_direct.get("username", ""),
        key="myqima_direct_user",
      )
    with col2:
      _direct_pwd = st.text_input(
        "myQIMA 密码", type="password",
        value=_default_direct.get("password", ""),
        key="myqima_direct_pwd",
      )
  else:
    col1, col2 = st.columns(2)
    with col1:
      _ppsso_cid_val = st.text_input(
        "Company ID", value=_myqima_cfg.get("companyId", ""),
        key="myqima_ppsso_cid",
      )
    with col2:
      st.text_input(
        "PPSO URL",
        value=_default_ppsso.get("url", ""),
        disabled=True, key="myqima_ppsso_url",
      )
    col1, col2 = st.columns(2)
    with col1:
      _ppsso_user_val = st.text_input(
        "Backoffice 账号", value=_default_ppsso.get("backofficeUsername", ""),
        key="myqima_ppsso_user",
      )
    with col2:
      _ppsso_pwd_val = st.text_input(
        "Backoffice 密码", type="password",
        value=_default_ppsso.get("backofficePassword", ""),
        key="myqima_ppsso_pwd",
      )

  # LOB + Booking 类型
  col1, col2 = st.columns(2)
  with col1:
    _lob = st.selectbox(
      "业务线", list(LOB_BOOKING_TYPES.keys()),
      key="myqima_lob",
    )
  with col2:
    _bt_list = LOB_BOOKING_TYPES[_lob]
    _booking_type = st.selectbox("下单类型", _bt_list, key="myqima_bt")

  # EA / ENVA 子标准
  _ea_variant = None
  _enva_variant = None
  if _booking_type == "EA":
    _ea_variant = st.selectbox(
      "EA 子标准", EA_VARIANTS, key="myqima_ea",
    )
  elif _booking_type == "ENVA":
    _enva_variant = st.selectbox(
      "ENVA Audit Guidelines", ENVA_VARIANTS, key="myqima_enva",
    )

  col1, col2 = st.columns(2)
  with col1:
    _product_count = st.number_input(
      "产品数量", min_value=1, max_value=10, value=1,
      key="myqima_product_count",
    )
  with col2:
    _dry_run = st.checkbox("Dry Run (不提交)", key="myqima_dry_run")

  # 高级设置
  with st.expander("⚙️ 高级设置"):
    _playwright_path = st.text_input(
      "Playwright 项目路径",
      value=_default_path or "D:\\pythonProject\\playwright",
      key="myqima_playwright_path",
      help="myQIMA booking-flow Playwright 项目的根目录路径",
    )

  st.markdown("---")
  st.subheader("🔄 四业务线回归测试")
  st.caption(
    "对 Inspection / Audit / Qcore / Certis 四条业务线各执行一次下单。"
    "复用上方 myQIMA 账号、产品数量、Dry Run 与 Playwright 路径。"
  )

  _reg_mode = st.radio(
    "下单类型",
    ["随机", "指定"],
    horizontal=True,
    key="myqima_reg_mode",
    help="随机：每条业务线从可选类型中随机选一个；指定：为每条业务线手动选择",
  )

  _reg_specified: dict[str, str] = {}
  if _reg_mode == "指定":
    _reg_cols = st.columns(2)
    for _i, _reg_lob in enumerate(["Inspection", "Audit", "Qcore", "Certis"]):
      with _reg_cols[_i % 2]:
        _reg_specified[_reg_lob] = st.selectbox(
          f"{_reg_lob}",
          LOB_BOOKING_TYPES[_reg_lob],
          key=f"myqima_reg_bt_{_reg_lob}",
        )

  _reg_stop_on_fail = st.checkbox(
    "遇错即停",
    value=False,
    key="myqima_reg_stop_on_fail",
    help="勾选后，任一条业务线失败则不再继续后续业务线",
  )

  _reg_col_run, _reg_col_clear = st.columns(2)
  with _reg_col_run:
    _btn_reg = st.button(
      "🔄 开始回归测试",
      use_container_width=True,
      key="btn_myqima_regression",
      disabled=st.session_state.myqima_regression_running,
    )
  with _reg_col_clear:
    if st.button("🗑️ 清空回归结果", use_container_width=True, key="btn_myqima_reg_clear"):
      st.session_state.myqima_regression_summary = None
      st.rerun()

  if _btn_reg:
    from modules._myqima_booking._config_builder import BookingConfig
    from modules._myqima_booking._regression_logic import build_regression_cases
    from modules._myqima_booking._regression_runner import (
      MyqimaRegressionRunner,
      RegressionCaseResult,
      RegressionRunSummary,
    )

    if _login_method != "myQIMA 账号":
      st.error("回归测试仅支持 myQIMA 账号登录，请切换登录方式")
    elif not _direct_user or not _direct_pwd:
      st.error("请输入 myQIMA 账号和密码")
    elif not _playwright_path:
      st.error("请配置 Playwright 项目路径")
    else:
      st.session_state.myqima_regression_running = True
      try:
        _reg_mode_key = "random" if _reg_mode == "随机" else "specified"
        _cases = build_regression_cases(
          mode=_reg_mode_key,
          specified=_reg_specified if _reg_mode_key == "specified" else None,
        )

        _base_cfg = BookingConfig(
          login_type="myqima",
          booking_type="PSI",
          product_count=_product_count,
          dry_run=_dry_run,
          direct_username=_direct_user,
          direct_password=_direct_pwd,
        )

        _reg_runner = MyqimaRegressionRunner(_playwright_path)
        _reg_log_box = st.empty()
        _reg_log_lines: list[str] = []
        _reg_summary = None

        with st.spinner("正在执行四业务线回归测试..."):
          for _evt in _reg_runner.stream(
            _cases, _base_cfg, stop_on_fail=_reg_stop_on_fail,
          ):
            if isinstance(_evt, str):
              _reg_log_lines.append(_evt)
              if len(_reg_log_lines) % 3 == 0:
                _reg_log_box.code("\n".join(_reg_log_lines[-40:]), language="text")
            elif isinstance(_evt, RegressionCaseResult):
              _reg_log_lines.append(
                f"--- {_evt.case.lob}/{_evt.case.booking_type}: "
                f"{'PASS' if _evt.result.success else 'FAIL'} ---"
              )
            elif isinstance(_evt, RegressionRunSummary):
              _reg_summary = _evt

        st.session_state.myqima_regression_summary = {
          "summary": _reg_summary,
          "logs": _reg_log_lines,
          "cases_plan": [
            {"lob": c.lob, "booking_type": c.booking_type} for c in _cases
          ],
        }
      except Exception as _reg_ex:
        st.error(f"回归测试异常: {_reg_ex}")
      finally:
        st.session_state.myqima_regression_running = False
        st.rerun()

  _prev = st.session_state.myqima_regression_summary
  if _prev and _prev.get("summary"):
    _s = _prev["summary"]
    st.markdown("#### 📊 回归结果汇总")
    _m1, _m2, _m3 = st.columns(3)
    _m1.metric("通过", f"{_s.passed_count}/{len(_s.case_results)}")
    _m2.metric("失败", _s.failed_count)
    _m3.metric("耗时", f"{_s.duration_seconds:.1f}s")

    _rows = []
    for _cr in _s.case_results:
      _rows.append({
        "业务线": _cr.case.lob,
        "下单类型": _cr.case.booking_type,
        "状态": "✅" if _cr.result.success else "❌",
        "Order ID": _cr.result.order_id or "-",
        "QIMA Ref": _cr.result.qima_ref or "-",
        "错误": _cr.result.error or "-",
      })
    st.dataframe(_rows, use_container_width=True, hide_index=True)

    with st.expander("📋 回归日志"):
      st.code("\n".join(_prev.get("logs", [])[-200:]), language="text")

  if st.button("▶️ 开始下单", use_container_width=True, key="btn_myqima"):
    from modules._myqima_booking._config_builder import BookingConfig, build_ppsso_url
    from modules._myqima_booking._booking_runner import BookingRunner

    _errors = []
    if _login_method == "myQIMA 账号":
      if not _direct_user or not _direct_pwd:
        _errors.append("请输入 myQIMA 账号和密码")
      _login_type = "myqima"
    else:
      if not _ppsso_cid_val:
        _errors.append("请输入 Company ID")
      if not _ppsso_user_val or not _ppsso_pwd_val:
        _errors.append("请输入 Backoffice 账号和密码")
      _login_type = "ppsso"

    if _errors:
      for _e in _errors:
        st.error(_e)
    else:
      # 保存 playwright_project_path 到配置文件
      if _curr_user and _playwright_path:
        try:
          with open(_cfg_path, encoding="utf-8") as _fh:
            _all_cfg = json.load(_fh)
          if "users" not in _all_cfg:
            _all_cfg["users"] = {}
          if _curr_user not in _all_cfg["users"]:
            _all_cfg["users"][_curr_user] = {}
          if "myqima" not in _all_cfg["users"][_curr_user]:
            _all_cfg["users"][_curr_user]["myqima"] = {}
          _all_cfg["users"][_curr_user]["myqima"]["playwright_project_path"] = _playwright_path
          with open(_cfg_path, "w", encoding="utf-8") as _fh:
            json.dump(_all_cfg, _fh, indent=2, ensure_ascii=False)
        except Exception as _ex:
            import logging
            logging.warning(f"保存 playwright_project_path 失败: {_ex}")

      _ppsso_url = ""
      if _login_type == "ppsso":
        _ppsso_url = _default_ppsso.get("url", "") or build_ppsso_url(_ppsso_cid_val)

      _config = BookingConfig(
        login_type=_login_type,
        booking_type=_booking_type,
        product_count=_product_count,
        dry_run=_dry_run,
        direct_username=_direct_user if _login_method == "myQIMA 账号" else "",
        direct_password=_direct_pwd if _login_method == "myQIMA 账号" else "",
        company_id=_ppsso_cid_val if _login_method != "myQIMA 账号" else "",
        ppsso_url=_ppsso_url,
        ppsso_username=_ppsso_user_val if _login_method != "myQIMA 账号" else "",
        ppsso_password=_ppsso_pwd_val if _login_method != "myQIMA 账号" else "",
        ea_variant=_ea_variant,
        enva_variant=_enva_variant,
      )

      _log_box = st.empty()
      _log_lines = []
      _run_result = None

      try:
        _runner = BookingRunner(_playwright_path)
        for _item in _runner.stream(_config.to_dict()):
          if isinstance(_item, str):
            _log_lines.append(_item)
            if len(_log_lines) % 5 == 0:
              _log_box.code("\n".join(_log_lines[-50:]), language="text")
          else:
            _run_result = _item

        _log_box.code("\n".join(_log_lines[-100:]), language="text")

        if _run_result and _run_result.success:
          st.success("✅ 下单流程执行完成")
          if _run_result.order_id:
            col_a, col_b, col_c, _ = st.columns(4)
            with col_a:
              st.metric("Order ID", _run_result.order_id)
            with col_b:
              st.metric("QIMA Ref", _run_result.qima_ref)
            with col_c:
              st.metric("Total Amount", _run_result.total_amount if _run_result.total_amount else "N/A")
          with st.expander("📋 完整日志"):
            st.code("\n".join(_log_lines), language="text")
        elif _run_result:
          st.error(f"❌ 执行失败: {_run_result.error}")
          with st.expander("📋 错误日志"):
            st.code("\n".join(_log_lines[-50:]), language="text")
      except Exception as _ex:
        st.error(f"❌ 执行异常: {_ex}")
        if _log_lines:
          with st.expander("📋 日志"):
            st.code("\n".join(_log_lines), language="text")


# ── 11. PR URL 批量访问 ──
with st.expander("🌐 PR URL 批量访问", expanded=False):
  st.markdown("输入多个 PR URL（每行一个），点击按钮即可在系统默认浏览器中批量打开。")

  pr_url_input = st.text_area(
    "请输入 PR URL（每行一个）",
    value="",
    placeholder="例如：\nhttps://github.com/example/pr1\nhttps://github.com/example/pr2",
    key="pr_url_input",
    height=200,
  )

  if not pr_url_input:
    st.session_state.pr_url_open_result = None

  if st.session_state.pr_url_open_result:
    st.caption(st.session_state.pr_url_open_result)

  if st.button("Open URL", use_container_width=True, type="primary", key="btn_open_pr_url"):
    if not pr_url_input:
      st.session_state.pr_url_open_result = None
      st.warning("⚠️ 请输入有效的 PR URL")
    else:
      urls = []
      for url in pr_url_input.split("\n"):
        url = url.strip().replace('"', "").replace("'", "")
        if url:
          urls.append(url)

      if not urls:
        st.session_state.pr_url_open_result = None
        st.warning("⚠️ 请输入有效的 PR URL（已过滤空行和无效 URL）")
      else:
        try:
          browser = webbrowser.get()
          opened_count = 0
          for i, url in enumerate(urls):
            try:
              browser.open(url)
              opened_count += 1
              if i < len(urls) - 1:
                time.sleep(0.3)
            except Exception as e:
              st.warning(f"⚠️ 无法打开: {url} - {e}")
          st.session_state.pr_url_open_result = (
            f"成功打开 {opened_count} 个 URL / 共输入 {len(urls)} 个 URL"
          )
          st.rerun()
        except Exception as e:
          logging.error("打开 PR URL 失败: %s", e)
          st.error(f"打开 URL 失败: {e}")


# ── 页脚 ──
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
  <p>🧪 Test Tools v1.0 | 全部工具在本地运行</p>
</div>
""", unsafe_allow_html=True)

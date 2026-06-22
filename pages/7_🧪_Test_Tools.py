"""
Test Tools - 测试工具集页面
将 9 个测试小工具集成到 Streamlit 界面
"""

import streamlit as st
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules._test_tools._api_perf_test import (
  APIPerformanceTester, TestConfig, parse_curl_command,
)
from modules._test_tools._clean_download import clean_download_files, format_size
from modules._test_tools._create_aca_account import create_aca_account, AccountInfo
from modules._test_tools._create_prefilled_link import PaymentLinkGenerator
from modules._test_tools._generate_pdf import generate_minimal_pdf
from modules._test_tools._generate_photo import generate_random_photos, generate_number_photos
from modules._test_tools._get_photo_from_url import TESLA_MODEL_MAP, download_tesla_images
from modules._test_tools._python_auto_gui import MouseMover
from modules._test_tools._shein_order import SheinOrderFlow
from modules._myqima_booking._config_builder import LOB_BOOKING_TYPES, EA_VARIANTS, ENVA_VARIANTS

st.set_page_config(page_title="Test Tools", page_icon="🧪", layout="wide")

st.title("🧪 Test Tools")
st.markdown("日常测试辅助工具集合，全部在本地运行。")

# Initialize session_state
if "mouse_mover" not in st.session_state:
  st.session_state.mouse_mover = MouseMover()

if "shein_logs" not in st.session_state:
  st.session_state.shein_logs = []


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
    link_bu = st.selectbox("BU", ["your-org", "your-org-wqs", "your-org-certis"], key="link_bu")

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
            st.success("✅ 生成成功")
            if result.link_url:
              st.code(result.link_url, language="text")
            else:
              st.info("响应已返回但未包含 linkUrl，可查看下方详细数据")
            if result.sign:
              st.text(f"Sign: {result.sign}")
            if result.request_data:
              with st.expander("请求数据"):
                st.json(result.request_data)
          else:
            st.error(f"生成失败: {result.error_message}")
        except Exception as e:
          st.error(str(e))


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

  _direct_user = ""
  _direct_pwd = ""
  _ppsso_cid_val = ""
  _ppsso_user_val = ""
  _ppsso_pwd_val = ""

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

  col1, col2 = st.columns(2)
  with col1:
    _lob = st.selectbox(
      "业务线", list(LOB_BOOKING_TYPES.keys()),
      key="myqima_lob",
    )
  with col2:
    _bt_list = LOB_BOOKING_TYPES[_lob]
    _booking_type = st.selectbox("下单类型", _bt_list, key="myqima_bt")

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
    _dry_run = st.checkbox("Dry Run（仅生成配置，不执行下单）", value=True, key="myqima_dry_run")

  _playwright_path = st.text_input(
    "Playwright 项目路径",
    value=_default_path,
    placeholder=r"D:\pythonProject\playwright",
    help="指向包含 myqima-booking-flow 测试脚本的 Playwright 项目根目录",
    key="myqima_playwright_path",
  )

  if st.button("🚀 开始下单", type="primary", use_container_width=True, key="myqima_start"):
    from modules._myqima_booking._config_builder import BookingConfig
    from modules._myqima_booking._booking_runner import BookingRunner

    if not _playwright_path:
      st.error("❌ 请输入 Playwright 项目路径")
    else:
      config = BookingConfig(
        login_type="myqima" if _login_method == "myQIMA 账号" else "ppsso",
        booking_type=_booking_type,
        product_count=_product_count,
        dry_run=_dry_run,
        direct_username=_direct_user,
        direct_password=_direct_pwd,
        company_id=_ppsso_cid_val,
        ppsso_username=_ppsso_user_val,
        ppsso_password=_ppsso_pwd_val,
        ea_variant=_ea_variant,
        enva_variant=_enva_variant,
      )

      runner = BookingRunner(_playwright_path)
      status = st.status("⏳ 执行下单流程...", expanded=True)
      with status:
        for item in runner.stream(config.to_dict()):
          if isinstance(item, str):
            status.write(item)
            st.session_state.myqima_last_log = item
          else:
            if item.success:
              st.success("✅ 下单成功！")
              if item.order_id:
                st.info(f"📋 Order ID: `{item.order_id}`")
              if item.qima_ref:
                st.info(f"📋 QIMA Ref: `{item.qima_ref}`")
            else:
              st.error(f"❌ 下单失败: {item.error}")

  if st.button("🗑️ 清空日志", key="myqima_clear"):
    st.rerun()

# ── 页脚 ──
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
  <p>🧪 Test Tools v1.0 | 全部工具在本地运行</p>
</div>
""", unsafe_allow_html=True)

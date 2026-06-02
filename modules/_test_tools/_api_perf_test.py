"""
API 性能测试核心逻辑
"""

import asyncio
import time
import statistics
import aiohttp
import requests
import concurrent.futures
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse, parse_qs


@dataclass
class TestConfig:
  url: str
  method: str = "GET"
  headers: Dict[str, str] = None
  params: Dict[str, str] = None
  data: Dict[str, Any] = None
  concurrent_users: int = 10
  total_requests: int = 100
  duration_seconds: int = 60
  timeout: int = 30
  test_mode: str = "requests"


@dataclass
class RequestResult:
  success: bool
  response_time: float
  status_code: int
  response_size: int
  error_message: str = ""
  timestamp: datetime = None

  def __post_init__(self):
    if self.timestamp is None:
      self.timestamp = datetime.now()


@dataclass
class TestReport:
  total_requests: int
  successful_requests: int
  failed_requests: int
  success_rate: float
  average_response_time: float
  median_response_time: float
  min_response_time: float
  max_response_time: float
  p75_response_time: float
  p90_response_time: float
  p95_response_time: float
  p99_response_time: float
  std_dev_response_time: float
  requests_per_second: float
  total_data_transferred: int
  test_duration: float
  concurrent_users: int
  status_code_distribution: Dict[int, int] = None
  error_distribution: Dict[str, int] = None


class APIPerformanceTester:
  def __init__(self, config: TestConfig):
    self.config = config
    self.results: List[RequestResult] = []
    self.session = requests.Session()
    if self.config.headers:
      self.session.headers.update(self.config.headers)

  def single_request_sync(self) -> RequestResult:
    start_time = time.time()
    try:
      if self.config.method.upper() == "GET":
        response = self.session.get(
          self.config.url, params=self.config.params, timeout=self.config.timeout
        )
      elif self.config.method.upper() == "POST":
        response = self.session.post(
          self.config.url, json=self.config.data, params=self.config.params, timeout=self.config.timeout
        )
      else:
        raise ValueError(f"不支持的HTTP方法: {self.config.method}")
      response_time = time.time() - start_time
      return RequestResult(
        success=response.status_code < 400,
        response_time=response_time,
        status_code=response.status_code,
        response_size=len(response.content),
      )
    except Exception as e:
      response_time = time.time() - start_time
      return RequestResult(
        success=False, response_time=response_time, status_code=0,
        response_size=0, error_message=str(e),
      )

  async def single_request_async(self, session: aiohttp.ClientSession) -> RequestResult:
    start_time = time.time()
    try:
      if self.config.method.upper() == "GET":
        async with session.get(
          self.config.url, params=self.config.params,
          timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        ) as response:
          content = await response.read()
          response_time = time.time() - start_time
          return RequestResult(
            success=response.status < 400, response_time=response_time,
            status_code=response.status, response_size=len(content),
          )
      elif self.config.method.upper() == "POST":
        async with session.post(
          self.config.url, json=self.config.data, params=self.config.params,
          timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        ) as response:
          content = await response.read()
          response_time = time.time() - start_time
          return RequestResult(
            success=response.status < 400, response_time=response_time,
            status_code=response.status, response_size=len(content),
          )
      else:
        raise ValueError(f"不支持的HTTP方法: {self.config.method}")
    except Exception as e:
      response_time = time.time() - start_time
      return RequestResult(
        success=False, response_time=response_time, status_code=0,
        response_size=0, error_message=str(e),
      )

  def run_sync_test(self) -> List[RequestResult]:
    results = []
    target_total = self.config.total_requests
    num_workers = self.config.concurrent_users
    base_per_worker = target_total // num_workers
    remainder = target_total % num_workers

    def worker(worker_idx: int):
      worker_results = []
      count = base_per_worker + (1 if worker_idx < remainder else 0)
      for _ in range(count):
        worker_results.append(self.single_request_sync())
      return worker_results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
      futures = [executor.submit(worker, i) for i in range(num_workers)]
      for future in concurrent.futures.as_completed(futures):
        results.extend(future.result())
    return results

  async def run_async_test(self) -> List[RequestResult]:
    connector = aiohttp.TCPConnector(limit=self.config.concurrent_users)
    headers = self.config.headers or {}
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
      if self.config.test_mode == "requests":
        tasks = [asyncio.create_task(self.single_request_async(session)) for _ in range(self.config.total_requests)]
        return await asyncio.gather(*tasks)
      else:
        results = []
        end_time = time.time() + self.config.duration_seconds
        while time.time() < end_time:
          tasks = []
          for _ in range(self.config.concurrent_users):
            if time.time() >= end_time:
              break
            tasks.append(asyncio.create_task(self.single_request_async(session)))
          if tasks:
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results

  def run_duration_test(self) -> List[RequestResult]:
    results = []
    end_time = time.time() + self.config.duration_seconds

    def worker():
      worker_results = []
      while time.time() < end_time:
        worker_results.append(self.single_request_sync())
        time.sleep(0.01)
      return worker_results

    with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_users) as executor:
      futures = [executor.submit(worker) for _ in range(self.config.concurrent_users)]
      for future in concurrent.futures.as_completed(futures):
        results.extend(future.result())
    return results

  def generate_report(self, results: List[RequestResult]) -> TestReport:
    if not results:
      raise ValueError("没有测试结果可生成报告")
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    times = [r.response_time for r in successful]
    timestamps = [r.timestamp for r in results]
    test_duration = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) > 1 else 1
    rps = len(results) / test_duration if test_duration > 0 else 0
    total_data = sum(r.response_size for r in successful)

    avg = statistics.mean(times) if times else 0
    median = statistics.median(times) if times else 0
    min_t = min(times) if times else 0
    max_t = max(times) if times else 0
    sorted_times = sorted(times)
    n = len(sorted_times)
    p75 = sorted_times[int(n * 0.75)] if n else 0
    p90 = sorted_times[int(n * 0.90)] if n else 0
    p95 = sorted_times[int(n * 0.95)] if n else 0
    p99 = sorted_times[int(n * 0.99)] if n else 0
    std_dev = statistics.stdev(times) if n > 1 else 0

    statusDist: Dict[int, int] = {}
    for r in results:
      statusDist[r.status_code] = statusDist.get(r.status_code, 0) + 1

    errDist: Dict[str, int] = {}
    for r in failed:
      key = "timeout" if "timeout" in r.error_message.lower() else \
            "connection" if "connection" in r.error_message.lower() else \
            "http_error" if r.status_code >= 400 else \
            "other"
      errDist[key] = errDist.get(key, 0) + 1

    return TestReport(
      total_requests=len(results),
      successful_requests=len(successful),
      failed_requests=len(failed),
      success_rate=len(successful) / len(results) * 100 if results else 0,
      average_response_time=avg, median_response_time=median,
      min_response_time=min_t, max_response_time=max_t,
      p75_response_time=p75, p90_response_time=p90,
      p95_response_time=p95, p99_response_time=p99,
      std_dev_response_time=std_dev,
      requests_per_second=rps, total_data_transferred=total_data,
      test_duration=test_duration, concurrent_users=self.config.concurrent_users,
      status_code_distribution=statusDist,
      error_distribution=errDist,
    )

  def create_charts(self, results: List[RequestResult], report: TestReport):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    successful = [r for r in results if r.success]
    times_ms = [r.response_time * 1000 for r in successful]

    axes[0, 0].hist(times_ms, bins=50, alpha=0.7, color='skyblue', edgecolor='black')
    axes[0, 0].set_title('响应时间分布 (毫秒)')
    axes[0, 0].set_xlabel('响应时间 (ms)')
    axes[0, 0].set_ylabel('频次')
    axes[0, 0].axvline(report.average_response_time * 1000, color='red', linestyle='--', label=f'平均值: {report.average_response_time * 1000:.1f}ms')
    axes[0, 0].legend()

    timestamps = [r.timestamp for r in results]
    ts_times = [r.response_time * 1000 for r in results]
    axes[0, 1].plot(timestamps, ts_times, alpha=0.6, linewidth=0.5)
    axes[0, 1].set_title('响应时间时间序列')
    axes[0, 1].set_xlabel('时间')
    axes[0, 1].set_ylabel('响应时间 (ms)')
    axes[0, 1].tick_params(axis='x', rotation=45)

    success_count = len(successful)
    failure_count = len(results) - success_count
    if failure_count > 0:
      axes[1, 0].pie(
        [success_count, failure_count],
        labels=[f'成功 ({success_count})', f'失败 ({failure_count})'],
        colors=['lightgreen', 'lightcoral'], autopct='%1.1f%%'
      )
    else:
      axes[1, 0].pie([success_count], labels=[f'成功 ({success_count})'], colors=['lightgreen'], autopct='%1.1f%%')
    axes[1, 0].set_title('请求成功率')

    axes[1, 1].axis('off')
    scDist = report.status_code_distribution or {}
    scLine = "  ".join([f"{k}: {v}" for k, v in sorted(scDist.items())])
    summary = (
      f"性能测试摘要报告\n\n"
      f"总请求数: {report.total_requests:,}\n"
      f"成功请求数: {report.successful_requests:,}\n"
      f"成功率: {report.success_rate:.2f}%\n"
      f"状态码分布: {scLine}\n\n"
      f"响应时间 (毫秒):\n"
      f"• 平均: {report.average_response_time * 1000:.2f}\n"
      f"• 中位数: {report.median_response_time * 1000:.2f}\n"
      f"• 标准差: {report.std_dev_response_time * 1000:.2f}\n"
      f"• 最小: {report.min_response_time * 1000:.2f}\n"
      f"• 最大: {report.max_response_time * 1000:.2f}\n"
      f"• P75: {report.p75_response_time * 1000:.2f}\n"
      f"• P90: {report.p90_response_time * 1000:.2f}\n"
      f"• P95: {report.p95_response_time * 1000:.2f}\n"
      f"• P99: {report.p99_response_time * 1000:.2f}\n\n"
      f"吞吐量: {report.requests_per_second:.2f} RPS\n"
      f"并发用户数: {report.concurrent_users}\n"
      f"测试持续时间: {report.test_duration:.2f} 秒\n"
      f"数据传输量: {report.total_data_transferred / 1024 / 1024:.2f} MB\n"
    )
    axes[1, 1].text(0.1, 0.5, summary, fontsize=10, verticalalignment='center',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
    plt.tight_layout()
    return fig


def _extractQuotedValue(text: str, startIdx: int, quoteChar: str = "'") -> tuple[Optional[str], int]:
  """Extract a quoted value starting from the given index. Returns (value, endIdx) or (None, startIdx)."""
  idx = text.find(quoteChar, startIdx)
  if idx == -1:
    return None, startIdx
  end = text.find(quoteChar, idx + 1)
  if end == -1:
    return None, startIdx
  return text[idx + 1:end], end + 1


def parse_curl_command(curl_command: str) -> TestConfig:
  lines = curl_command.strip().split('\n')
  url = None
  for line in lines:
    line = line.strip()
    if line.startswith('curl'):
      val, _ = _extractQuotedValue(line, 0, "'")
      if val:
        url = val
      else:
        val, _ = _extractQuotedValue(line, 0, '"')
        if val:
          url = val
      break
  if not url:
    raise ValueError("无法从curl命令中提取URL")
  headers = {}
  for line in lines:
    line = line.strip()
    idx = 0
    while True:
      headerPos = line.find('--header', idx)
      if headerPos == -1:
        break
      headerVal, idx = _extractQuotedValue(line, headerPos + len('--header'))
      if headerVal and ':' in headerVal:
        key, value = headerVal.split(':', 1)
        headers[key.strip()] = value.strip()
  parsed_url = urlparse(url)
  base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
  params = parse_qs(parsed_url.query)
  params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in params.items()}
  config = TestConfig(url=base_url, headers=headers, params=params)
  if '-X POST' in curl_command or ' -d ' in curl_command:
    config.method = "POST"
  return config

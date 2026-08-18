"""Prod 快速验证：调用 Playwright prod-login.spec.ts 并流式输出日志。"""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SPEC_RELATIVE = Path("tests") / "prod-login.spec.ts"
PASSED_RE = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
FAILED_RE = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
SKIPPED_RE = re.compile(r"(\d+)\s+skipped", re.IGNORECASE)

# Playwright list reporter: "  ok  1 [chromium] › path › suite › title (34.1s)"
CASE_LINE_RE = re.compile(
  r"^\s*(ok|x|-|±|✓|✘|✖)\s+(\d+)\s+"
  r"(?:\[[^\]]+\]\s+›\s+)?"
  r"(.+?)\s+\(([^)]+)\)\s*$",
  re.IGNORECASE,
)

STATUS_MAP = {
  "ok": "passed",
  "✓": "passed",
  "x": "failed",
  "✘": "failed",
  "✖": "failed",
  "-": "skipped",
  "±": "flaky",
}


@dataclass
class ProdLoginCaseResult:
  """单条用例结果。"""

  index: int
  status: str
  title: str
  duration: str = ""
  full_title: str = ""


@dataclass
class ProdLoginResult:
  """prod-login 测试运行结果。"""

  success: bool = False
  exit_code: int | None = None
  passed: int = 0
  failed: int = 0
  skipped: int = 0
  error: str = ""
  logs: list[str] = field(default_factory=list)
  cases: list[ProdLoginCaseResult] = field(default_factory=list)


def isValidPlaywrightProject(path: Path) -> bool:
  """判断目录是否为包含 prod-login.spec.ts 的 Playwright 项目。"""
  return path.is_dir() and (path / SPEC_RELATIVE).is_file()


def resolvePlaywrightProjectPath(
  userPath: str | None,
  webtoolsRoot: Path | None = None,
) -> Path:
  """解析 Playwright 项目路径：用户配置优先，其次 webtools 兄弟目录 playwright。

  Args:
    userPath: 用户配置的路径，可为空。
    webtoolsRoot: webtools 仓库根目录；默认取本文件向上两级。

  Returns:
    解析后的绝对路径。

  Raises:
    FileNotFoundError: 找不到有效项目（须含 tests/prod-login.spec.ts）。
  """
  if webtoolsRoot is None:
    webtoolsRoot = Path(__file__).resolve().parents[2]

  candidates: list[Path] = []
  if userPath and str(userPath).strip():
    candidates.append(Path(str(userPath).strip()).expanduser())

  candidates.append((webtoolsRoot.parent / "playwright").resolve())

  for candidate in candidates:
    try:
      resolved = candidate.resolve()
    except OSError:
      continue
    if isValidPlaywrightProject(resolved):
      return resolved

  raise FileNotFoundError(
    "未找到有效的 Playwright 项目（需包含 tests/prod-login.spec.ts）。"
    "请在配置中设置 myqima.playwright_project_path，"
    "或将 playwright 仓库放在与 webtools 同级的目录。"
  )


def parseProdLoginSummary(lines: list[str]) -> dict[str, int]:
  """从 Playwright 输出中解析通过/失败/跳过数量。"""
  passed = 0
  failed = 0
  skipped = 0
  for line in lines:
    mPass = PASSED_RE.search(line)
    if mPass:
      passed = int(mPass.group(1))
    mFail = FAILED_RE.search(line)
    if mFail:
      failed = int(mFail.group(1))
    mSkip = SKIPPED_RE.search(line)
    if mSkip:
      skipped = int(mSkip.group(1))
  return {"passed": passed, "failed": failed, "skipped": skipped}


def parseProdLoginCaseLine(line: str) -> ProdLoginCaseResult | None:
  """解析 Playwright list reporter 的单条用例结果行。

  示例:
    ok  1 [chromium] › tests/prod-login.spec.ts:431:7 › suite › TC-01: ... (34.1s)
  """
  match = CASE_LINE_RE.match(line)
  if not match:
    return None

  rawStatus = match.group(1).lower()
  # 符号状态保持原样映射（✓/✘ 不走 lower 后的键）
  statusKey = match.group(1)
  status = STATUS_MAP.get(statusKey) or STATUS_MAP.get(rawStatus)
  if status is None:
    return None

  index = int(match.group(2))
  fullTitle = match.group(3).strip()
  duration = match.group(4).strip()
  # 取最后一个 › 后的短标题（通常为 TC-xx）
  parts = [p.strip() for p in re.split(r"\s*›\s*", fullTitle) if p.strip()]
  title = parts[-1] if parts else fullTitle

  return ProdLoginCaseResult(
    index=index,
    status=status,
    title=title,
    duration=duration,
    full_title=fullTitle,
  )


def parseProdLoginCases(lines: list[str]) -> list[ProdLoginCaseResult]:
  """从日志中提取全部用例结果（按 index 去重，后者覆盖前者）。"""
  byIndex: dict[int, ProdLoginCaseResult] = {}
  for line in lines:
    case = parseProdLoginCaseLine(line)
    if case is not None:
      byIndex[case.index] = case
  return [byIndex[i] for i in sorted(byIndex)]


def formatCaseStatusLabel(status: str) -> str:
  """将内部 status 转为展示标签。"""
  mapping = {
    "passed": "✅ 通过",
    "failed": "❌ 失败",
    "skipped": "⏭️ 跳过",
    "flaky": "⚠️ Flaky",
  }
  return mapping.get(status, status)


def casesToRows(cases: list[ProdLoginCaseResult]) -> list[dict[str, str | int]]:
  """将用例结果转为表格行。"""
  rows: list[dict[str, str | int]] = []
  for case in cases:
    rows.append({
      "#": case.index,
      "状态": formatCaseStatusLabel(case.status),
      "用例": case.title,
      "耗时": case.duration,
    })
  return rows


def _findNpx() -> str:
  """查找 npx 可执行文件路径。"""
  if platform.system() == "Windows":
    npxPath = shutil.which("npx.cmd") or shutil.which("npx")
    if npxPath:
      return npxPath
    raise FileNotFoundError("未找到 npx，请确认 Node.js 已安装并添加到 PATH")
  return "npx"


def _killProcessTree(proc: subprocess.Popen | None) -> None:
  """终止子进程及其进程树（Windows 用 taskkill）。"""
  if proc is None:
    return
  if platform.system() != "Windows":
    try:
      proc.kill()
      proc.wait()
    except Exception:
      pass
    return
  try:
    subprocess.run(
      ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      timeout=5,
    )
  except Exception as ex:
    logger.warning("终止 Playwright 进程失败: %s", ex)


class ProdLoginRunner:
  """在指定 Playwright 项目中运行 prod-login.spec.ts。"""

  def __init__(self, playwrightProjectPath: str | Path):
    """初始化 Runner。

    Args:
      playwrightProjectPath: Playwright 项目根目录。
    """
    self.playwrightPath = Path(playwrightProjectPath)

  def run(self, headed: bool = False, timeout: int = 1800) -> ProdLoginResult:
    """同步运行并返回最终结果。"""
    for item in self.stream(headed=headed, timeout=timeout):
      if isinstance(item, ProdLoginResult):
        return item
    return ProdLoginResult(error="未收到运行结果")

  def stream(
    self, headed: bool = False, timeout: int = 1800
  ) -> Iterator[str | ProdLoginResult]:
    """流式运行测试：逐行 yield 日志，最后 yield ProdLoginResult。

    Args:
      headed: True 时显示浏览器窗口。
      timeout: 等待进程结束的超时秒数。
    """
    result = ProdLoginResult()

    if not self.playwrightPath.exists():
      result.error = f"Playwright 项目路径不存在: {self.playwrightPath}"
      yield result
      return

    if not isValidPlaywrightProject(self.playwrightPath):
      result.error = (
        f"路径无效或缺少 {SPEC_RELATIVE.as_posix()}: {self.playwrightPath}"
      )
      yield result
      return

    try:
      npxCmd = _findNpx()
    except FileNotFoundError as ex:
      result.error = str(ex)
      yield result
      return

    # 使用正斜杠相对路径，Playwright/CLI 在 Windows 上也能识别
    specArg = SPEC_RELATIVE.as_posix()
    cmd = [
      npxCmd, "playwright", "test",
      specArg,
      "--project=chromium",
      "--workers=1",
    ]
    if headed:
      cmd.append("--headed")

    process: subprocess.Popen | None = None
    try:
      process = subprocess.Popen(
        cmd,
        cwd=str(self.playwrightPath.resolve()),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        creationflags=(
          subprocess.CREATE_NEW_PROCESS_GROUP
          if platform.system() == "Windows"
          else 0
        ),
      )

      assert process.stdout is not None
      for line in iter(process.stdout.readline, ""):
        line = line.rstrip("\n")
        result.logs.append(line)
        yield line

      process.wait(timeout=timeout)
      result.exit_code = process.returncode
      result.cases = parseProdLoginCases(result.logs)
      summary = parseProdLoginSummary(result.logs)
      result.passed = summary["passed"]
      result.failed = summary["failed"]
      result.skipped = summary["skipped"]
      # 汇总行缺失时，按用例列表回填计数
      if result.cases and (result.passed + result.failed + result.skipped == 0):
        result.passed = sum(1 for c in result.cases if c.status == "passed")
        result.failed = sum(1 for c in result.cases if c.status == "failed")
        result.skipped = sum(1 for c in result.cases if c.status == "skipped")
      result.success = process.returncode == 0
      if process.returncode != 0 and not result.error:
        result.error = f"进程退出码: {process.returncode}"
    except subprocess.TimeoutExpired:
      result.error = f"执行超时（超过 {timeout} 秒）"
    except Exception as ex:
      result.error = str(ex)
      logger.exception("ProdLoginRunner 执行异常")
    finally:
      _killProcessTree(process)

    yield result

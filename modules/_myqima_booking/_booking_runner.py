import subprocess
import json
import re
import shutil
import platform
from pathlib import Path
from dataclasses import dataclass, field


ORDER_ID_RE = re.compile(r'[Oo]rder\s*[Ii][Dd][:\s]+([a-fA-F0-9]{32})')
QIMA_REF_RE = re.compile(r'QIMA\s*[Rr]ef[:\s]+(Q\d{10}-\w{2})')


@dataclass
class BookingResult:
  order_id: str = ""
  qima_ref: str = ""
  success: bool = False
  error: str = ""
  logs: list[str] = field(default_factory=list)


def parse_log_line(line: str, result: BookingResult) -> None:
  m = ORDER_ID_RE.search(line)
  if m:
    result.order_id = m.group(1)
  m = QIMA_REF_RE.search(line)
  if m:
    result.qima_ref = m.group(1)


def _find_npx() -> str:
  if platform.system() == "Windows":
    npx_path = shutil.which("npx.cmd") or shutil.which("npx")
    if npx_path:
      return npx_path
    raise FileNotFoundError(
      "未找到 npx，请确认 Node.js 已安装并添加到 PATH"
    )
  return "npx"


class BookingRunner:
  def __init__(self, playwright_project_path: str):
    self.playwright_path = Path(playwright_project_path)
    self.config_dir = self.playwright_path / "tests" / "myqima-booking-flow"
    self.config_path = self.config_dir / "booking-config.json"

  def run(self, config_dict: dict) -> BookingResult:
    result = BookingResult()
    for item in self.stream(config_dict):
      if isinstance(item, str):
        result.logs.append(item)
      else:
        return item
    return result

  def stream(self, config_dict: dict, timeout: int = 300):
    npx_cmd = _find_npx()

    if not self.playwright_path.exists():
      yield BookingResult(
        error=f"Playwright 项目路径不存在: {self.playwright_path}"
      )
      return

    self.config_dir.mkdir(parents=True, exist_ok=True)
    self.config_path.write_text(
      json.dumps(config_dict, indent=2), encoding="utf-8"
    )

    result = BookingResult()

    try:
      process = subprocess.Popen(
        [
          npx_cmd, "playwright", "test",
          "tests/myqima-booking-flow/booking-flow.spec.ts",
          "--project=chromium",
        ],
        cwd=str(self.playwright_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
      )

      for line in iter(process.stdout.readline, ""):
        line = line.rstrip("\n")
        result.logs.append(line)
        parse_log_line(line, result)
        yield line

      process.wait(timeout=timeout)
      result.success = process.returncode == 0
      if process.returncode != 0 and not result.error:
        result.error = f"Process exited with code {process.returncode}"
    except subprocess.TimeoutExpired:
      process.kill()
      result.error = f"执行超时（超过 {timeout} 秒）"
    except Exception as e:
      result.error = str(e)
    finally:
      if self.config_path.exists():
        self.config_path.unlink()
    yield result

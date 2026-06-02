"""
鼠标自动移动工具（线程控制启停）
"""

import random
import time
import threading
from typing import Optional


class MouseMover:
  def __init__(self, interval: float = 15.0):
    self.interval = interval
    self._thread: Optional[threading.Thread] = None
    self._stop_event = threading.Event()
    self._is_running = False

  @property
  def is_running(self) -> bool:
    return self._is_running

  def start(self) -> None:
    if self._is_running:
      return
    self._stop_event.clear()
    self._is_running = True
    self._thread = threading.Thread(target=self._run, daemon=True)
    self._thread.start()

  def stop(self) -> None:
    if not self._is_running:
      return
    self._stop_event.set()
    self._is_running = False
    if self._thread:
      self._thread.join(timeout=5)
      self._thread = None

  def _run(self) -> None:
    try:
      import pyautogui
      screen_width, screen_height = pyautogui.size()
      while not self._stop_event.is_set():
        x = random.randint(0, screen_width - 1)
        y = random.randint(0, screen_height - 1)
        duration = random.uniform(0.1, 2.0)
        pyautogui.moveTo(x, y, duration=duration)
        pyautogui.click()
        self._stop_event.wait(self.interval)
    except ImportError:
      pass
    except Exception:
      pass
    finally:
      self._is_running = False

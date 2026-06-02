import pytest
from modules._test_tools._python_auto_gui import MouseMover


class TestMouseMover:
  def testInitialState(self):
    mover = MouseMover()
    assert mover.is_running is False

  def testStart(self):
    mover = MouseMover()
    mover.start()
    assert mover.is_running is True
    mover.stop()
    assert mover.is_running is False

  def testStartStopIdempotent(self):
    mover = MouseMover()
    mover.start()
    mover.start()
    assert mover.is_running is True
    mover.stop()
    mover.stop()
    assert mover.is_running is False

  def testInterval(self):
    mover = MouseMover(interval=30.0)
    assert mover.interval == 30.0
    mover.interval = 10.0
    assert mover.interval == 10.0

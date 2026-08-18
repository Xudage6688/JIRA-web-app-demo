"""Sequential runner for myQIMA four-LOB regression tests."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, Optional, Union

from modules._myqima_booking._config_builder import BookingConfig
from modules._myqima_booking._booking_runner import BookingRunner, BookingResult
from modules._myqima_booking._regression_logic import (
  RegressionCase,
  apply_case_to_config,
)


@dataclass
class RegressionCaseResult:
  case: RegressionCase
  result: BookingResult
  logs: list[str] = field(default_factory=list)


@dataclass
class RegressionRunSummary:
  case_results: list[RegressionCaseResult]
  all_passed: bool
  passed_count: int
  failed_count: int
  duration_seconds: float


ProgressEvent = Union[str, RegressionCaseResult, RegressionRunSummary]


class MyqimaRegressionRunner:
  """Run regression cases one-by-one via BookingRunner."""

  def __init__(self, playwright_project_path: str):
    self.playwright_path = playwright_project_path
    self._booking_runner = BookingRunner(playwright_project_path)

  def run(
    self,
    cases: list[RegressionCase],
    base_config: BookingConfig,
    stop_on_fail: bool = False,
  ) -> RegressionRunSummary:
    summary = None
    for event in self.stream(cases, base_config, stop_on_fail=stop_on_fail):
      if isinstance(event, RegressionRunSummary):
        summary = event
    assert summary is not None
    return summary

  def stream(
    self,
    cases: list[RegressionCase],
    base_config: BookingConfig,
    stop_on_fail: bool = False,
  ) -> Iterator[ProgressEvent]:
    start = time.monotonic()
    case_results: list[RegressionCaseResult] = []

    for idx, case in enumerate(cases):
      yield f"=== [{idx + 1}/{len(cases)}] {case.lob} / {case.booking_type} ==="

      config = apply_case_to_config(base_config, case)
      logs: list[str] = []
      result = BookingResult(success=False, error="No result returned")

      for item in self._booking_runner.stream(config.to_dict()):
        if isinstance(item, str):
          logs.append(item)
          yield item
        else:
          result = item

      case_result = RegressionCaseResult(case=case, result=result, logs=logs)
      case_results.append(case_result)
      yield case_result

      if not result.success and stop_on_fail:
        break

    passed = sum(1 for cr in case_results if cr.result.success)
    failed = len(case_results) - passed
    summary = RegressionRunSummary(
      case_results=case_results,
      all_passed=failed == 0 and len(case_results) == len(cases),
      passed_count=passed,
      failed_count=failed,
      duration_seconds=time.monotonic() - start,
    )
    yield summary

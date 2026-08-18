"""Tests for myQIMA four-LOB regression logic."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules._myqima_booking._regression_logic import (
  LOB_ORDER,
  RegressionCase,
  build_regression_cases,
  apply_case_to_config,
  pick_booking_type_for_lob,
)
from modules._myqima_booking._config_builder import (
  BookingConfig,
  LOB_BOOKING_TYPES,
  EA_VARIANTS,
  ENVA_VARIANTS,
)


def test_lob_order_has_four_business_lines():
  assert LOB_ORDER == ["Inspection", "Audit", "Qcore", "Certis"]
  assert len(LOB_ORDER) == 4


def test_build_regression_cases_specified_mode():
  specified = {
    "Inspection": "PSI",
    "Audit": "MA",
    "Qcore": "STS",
    "Certis": "SABER",
  }
  cases = build_regression_cases(mode="specified", specified=specified)
  assert len(cases) == 4
  assert cases[0] == RegressionCase(
    lob="Inspection", booking_type="PSI",
    ea_variant=None, enva_variant=None,
  )
  assert cases[1].booking_type == "MA"
  assert cases[2].booking_type == "STS"
  assert cases[3].booking_type == "SABER"


def test_build_regression_cases_random_mode_with_seed():
  cases_a = build_regression_cases(mode="random", seed=42)
  cases_b = build_regression_cases(mode="random", seed=42)
  assert len(cases_a) == 4
  assert cases_a == cases_b
  for case in cases_a:
    assert case.booking_type in LOB_BOOKING_TYPES[case.lob]


def test_build_regression_cases_ea_gets_ea_variant():
  specified = {
    "Inspection": "PSI",
    "Audit": "EA",
    "Qcore": "STS",
    "Certis": "SABER",
  }
  cases = build_regression_cases(mode="specified", specified=specified)
  audit_case = [c for c in cases if c.lob == "Audit"][0]
  assert audit_case.ea_variant == EA_VARIANTS[0]
  assert audit_case.enva_variant is None


def test_build_regression_cases_enva_gets_enva_variant():
  specified = {
    "Inspection": "PSI",
    "Audit": "ENVA",
    "Qcore": "STS",
    "Certis": "SABER",
  }
  cases = build_regression_cases(mode="specified", specified=specified)
  audit_case = [c for c in cases if c.lob == "Audit"][0]
  assert audit_case.enva_variant == ENVA_VARIANTS[0]
  assert audit_case.ea_variant is None


def test_pick_booking_type_for_lob_deterministic_with_seed():
  bt1 = pick_booking_type_for_lob("Inspection", seed=99)
  bt2 = pick_booking_type_for_lob("Inspection", seed=99)
  assert bt1 == bt2
  assert bt1 in LOB_BOOKING_TYPES["Inspection"]


def test_apply_case_to_config_overrides_booking_type():
  base = BookingConfig(
    login_type="myqima",
    booking_type="PSI",
    direct_username="user@test.com",
    direct_password="secret",
  )
  case = RegressionCase(
    lob="Audit", booking_type="EA",
    ea_variant="SMETA", enva_variant=None,
  )
  merged = apply_case_to_config(base, case)
  d = merged.to_dict()
  assert d["bookingType"] == "EA"
  assert d["eaVariant"] == "SMETA"
  assert d["loginType"] == "myqima"
  assert d["directAccount"]["username"] == "user@test.com"


def test_build_regression_cases_rejects_invalid_booking_type():
  specified = {
    "Inspection": "PSI",
    "Audit": "INVALID",
    "Qcore": "STS",
    "Certis": "SABER",
  }
  try:
    build_regression_cases(mode="specified", specified=specified)
    assert False, "should raise ValueError"
  except ValueError as e:
    assert "Audit" in str(e)


from unittest.mock import MagicMock, patch
from modules._myqima_booking._regression_runner import MyqimaRegressionRunner
from modules._myqima_booking._booking_runner import BookingResult


def test_regression_runner_runs_all_cases_sequentially():
  cases = build_regression_cases(mode="specified", specified={
    "Inspection": "PSI",
    "Audit": "MA",
    "Qcore": "STS",
    "Certis": "SABER",
  })
  base = BookingConfig(
    login_type="myqima",
    booking_type="PSI",
    direct_username="u@t.com",
    direct_password="pwd",
  )

  mock_results = [
    BookingResult(success=True, order_id="id1", qima_ref="Q1"),
    BookingResult(success=True, order_id="id2", qima_ref="Q2"),
    BookingResult(success=False, error="timeout"),
    BookingResult(success=True, order_id="id4", qima_ref="Q4"),
  ]
  call_count = {"n": 0}

  def fake_stream(config_dict):
    idx = call_count["n"]
    call_count["n"] += 1
    yield f"log line {idx}"
    yield mock_results[idx]

  mock_runner = MagicMock()
  mock_runner.stream.side_effect = fake_stream

  with patch(
    "modules._myqima_booking._regression_runner.BookingRunner",
    return_value=mock_runner,
  ):
    runner = MyqimaRegressionRunner("D:\\fake\\playwright")
    summary = runner.run(cases, base)

  assert call_count["n"] == 4
  assert len(summary.case_results) == 4
  assert summary.all_passed is False
  assert summary.passed_count == 3
  assert summary.failed_count == 1
  assert summary.case_results[2].result.error == "timeout"


def test_regression_runner_stops_on_first_failure_when_stop_on_fail():
  cases = build_regression_cases(mode="specified", specified={
    "Inspection": "PSI",
    "Audit": "MA",
    "Qcore": "STS",
    "Certis": "SABER",
  })
  base = BookingConfig(login_type="myqima", booking_type="PSI")

  def fake_stream(config_dict):
    yield "log"
    yield BookingResult(success=False, error="login failed")

  mock_runner = MagicMock()
  mock_runner.stream.side_effect = fake_stream

  with patch(
    "modules._myqima_booking._regression_runner.BookingRunner",
    return_value=mock_runner,
  ):
    runner = MyqimaRegressionRunner("D:\\fake\\playwright")
    summary = runner.run(cases, base, stop_on_fail=True)

  assert len(summary.case_results) == 1
  assert summary.all_passed is False

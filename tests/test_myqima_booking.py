"""Tests for myQIMA booking config builder."""
import json
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules._myqima_booking._config_builder import (
  BookingConfig,
  build_ppsso_url,
  LOB_BOOKING_TYPES,
  BookingType,
)
from modules._myqima_booking._booking_runner import parse_log_line, BookingResult, BookingRunner


def test_build_ppsso_url():
  url = build_ppsso_url("74CA94F460EC470499DCDADC7CB7C001")
  assert url == "https://ppsso.example.com/back-office/v2/company-profile/customer/74CA94F460EC470499DCDADC7CB7C001"


def test_config_builder_myqima():
  config = BookingConfig(
      login_type="myqima",
      booking_type="PSI",
      product_count=2,
      direct_username="test_user",
      direct_password="test_pass",
  )
  d = config.to_dict()
  assert d["loginType"] == "myqima"
  assert d["bookingType"] == "PSI"
  assert d["productCount"] == 2
  assert d["dryRun"] is False
  assert d["directAccount"]["username"] == "test_user"
  assert d["directAccount"]["password"] == "test_pass"


def test_config_builder_ppsso():
  config = BookingConfig(
      login_type="ppsso",
      booking_type="EA",
      company_id="TESTCID123",
      ppsso_username="back_user",
      ppsso_password="back_pass",
  )
  d = config.to_dict()
  assert d["loginType"] == "ppsso"
  assert d["bookingType"] == "EA"
  assert d["companyId"] == "TESTCID123"
  assert d["ppssoBackdoor"]["backofficeUsername"] == "back_user"
  assert d["ppssoBackdoor"]["backofficePassword"] == "back_pass"
  assert "ppsso.example.com" in d["ppssoBackdoor"]["url"]


def test_config_builder_dry_run():
  config = BookingConfig(
      login_type="myqima", booking_type="PSI",
      dry_run=True,
  )
  assert config.to_dict()["dryRun"] is True


def test_config_builder_ea_variant():
  config = BookingConfig(
      login_type="myqima", booking_type="EA",
      ea_variant="SMETA",
  )
  assert config.to_dict()["eaVariant"] == "SMETA"


def test_config_builder_enva_variant():
  config = BookingConfig(
      login_type="myqima", booking_type="ENVA",
      enva_variant="HIGG_FEM",
  )
  assert config.to_dict()["envaVariant"] == "HIGG_FEM"


def test_lob_booking_types_structure():
  assert "Inspection" in LOB_BOOKING_TYPES
  assert "Audit" in LOB_BOOKING_TYPES
  assert "Qcore" in LOB_BOOKING_TYPES
  assert "Certis" in LOB_BOOKING_TYPES
  assert "PSI" in LOB_BOOKING_TYPES["Inspection"]
  assert "EA" in LOB_BOOKING_TYPES["Audit"]
  assert "SABER" in LOB_BOOKING_TYPES["Certis"]


def test_ea_variants():
  from modules._myqima_booking._config_builder import EA_VARIANTS
  assert "QIMA_ETHICAL" in EA_VARIANTS
  assert "BSCI" in EA_VARIANTS


def test_enva_variants():
  from modules._myqima_booking._config_builder import ENVA_VARIANTS
  assert "QIMA" in ENVA_VARIANTS
  assert "HIGG_FEM" in ENVA_VARIANTS


def test_booking_type_enum_values():
  assert BookingType("PSI") == "PSI"
  assert BookingType("EA") == "EA"




def test_parse_log_line_order_id():
  result = BookingResult()
  parse_log_line("[12:30:01] Order ID: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", result)
  assert result.order_id == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


def test_parse_log_line_qima_ref():
  result = BookingResult()
  parse_log_line("[12:30:01] QIMA Ref: Q2026061201-AB", result)
  assert result.qima_ref == "Q2026061201-AB"


def test_parse_log_line_both():
  result = BookingResult()
  parse_log_line("[12:30:01] Order ID: abc123def456abc123def456abc123de", result)
  assert result.order_id == "abc123def456abc123def456abc123de"
  parse_log_line("[12:30:02] QIMA Ref: Q2026061201-XY", result)
  assert result.qima_ref == "Q2026061201-XY"


def test_parse_log_line_no_match():
  result = BookingResult()
  parse_log_line("[12:30:01] Login successful", result)
  assert result.order_id == ""
  assert result.qima_ref == ""


def test_booking_result_defaults():
  r = BookingResult()
  assert r.order_id == ""
  assert r.qima_ref == ""
  assert r.success is False
  assert r.error == ""
  assert r.logs == []


def test_runner_path_not_exists():
  runner = BookingRunner(r"D:\nonexistent_path_xyz")
  result = runner.run({"bookingType": "PSI"})
  assert result.success is False
  assert "不存在" in result.error


def test_runner_stream_yields_lines_then_result():
  with tempfile.TemporaryDirectory() as tmpdir:
    with patch("modules._myqima_booking._booking_runner.shutil.which", return_value="npx.cmd"):
      with patch("modules._myqima_booking._booking_runner.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = [
          "[12:30:01] Login successful\n",
          "[12:30:02] Booking completed\n",
          "[12:30:03] Order ID: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6\n",
          "[12:30:04] QIMA Ref: Q2026061201-AB\n",
          "",
        ]
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        runner = BookingRunner(tmpdir)
        items = list(runner.stream({"bookingType": "PSI"}))
        log_lines = [i for i in items if isinstance(i, str)]
        result = [i for i in items if isinstance(i, BookingResult)][0]

        assert len(log_lines) == 4
        assert "Login successful" in log_lines[0]
        assert "Order ID" in log_lines[2]
        assert result.success is True
        assert result.order_id == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        assert result.qima_ref == "Q2026061201-AB"

"""Pure functions for myQIMA four-LOB regression test planning."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, Optional

from modules._myqima_booking._config_builder import (
  BookingConfig,
  LOB_BOOKING_TYPES,
  EA_VARIANTS,
  ENVA_VARIANTS,
)

LOB_ORDER: list[str] = ["Inspection", "Audit", "Qcore", "Certis"]

RegressionMode = Literal["random", "specified"]


@dataclass(frozen=True)
class RegressionCase:
  lob: str
  booking_type: str
  ea_variant: Optional[str] = None
  enva_variant: Optional[str] = None


def pick_booking_type_for_lob(lob: str, seed: Optional[int] = None) -> str:
  """Pick one booking type from a LOB; seed makes random choice reproducible."""
  rng = random.Random(seed)
  return rng.choice(LOB_BOOKING_TYPES[lob])


def _resolve_variants(booking_type: str) -> tuple[Optional[str], Optional[str]]:
  if booking_type == "EA":
    return EA_VARIANTS[0], None
  if booking_type == "ENVA":
    return None, ENVA_VARIANTS[0]
  return None, None


def _validate_booking_type(lob: str, booking_type: str) -> None:
  allowed = LOB_BOOKING_TYPES.get(lob, [])
  if booking_type not in allowed:
    raise ValueError(
      f"业务线 {lob} 不支持下单类型 {booking_type}，可选: {allowed}"
    )


def build_regression_cases(
  mode: RegressionMode,
  specified: Optional[dict[str, str]] = None,
  seed: Optional[int] = None,
) -> list[RegressionCase]:
  """Build exactly one RegressionCase per LOB in LOB_ORDER."""
  cases: list[RegressionCase] = []
  for i, lob in enumerate(LOB_ORDER):
    if mode == "random":
      bt = pick_booking_type_for_lob(lob, seed=(None if seed is None else seed + i))
    else:
      if not specified or lob not in specified:
        raise ValueError(f"指定模式缺少业务线 {lob} 的下单类型")
      bt = specified[lob]
      _validate_booking_type(lob, bt)

    ea_v, enva_v = _resolve_variants(bt)
    cases.append(RegressionCase(
      lob=lob, booking_type=bt,
      ea_variant=ea_v, enva_variant=enva_v,
    ))
  return cases


def apply_case_to_config(base: BookingConfig, case: RegressionCase) -> BookingConfig:
  """Clone base config and override booking type + variants for one regression case."""
  return BookingConfig(
    login_type=base.login_type,
    booking_type=case.booking_type,
    product_count=base.product_count,
    dry_run=base.dry_run,
    direct_username=base.direct_username,
    direct_password=base.direct_password,
    company_id=base.company_id,
    ppsso_url=base.ppsso_url,
    ppsso_username=base.ppsso_username,
    ppsso_password=base.ppsso_password,
    ea_variant=case.ea_variant,
    enva_variant=case.enva_variant,
  )

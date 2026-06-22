from typing import Optional
import json

BookingType = str

LOB_BOOKING_TYPES: dict[str, list[str]] = {
  "Inspection": ["PSI", "PEO", "CLC", "DUPRO", "SC", "PM", "IPC", "SR"],
  "Audit": ["EA", "MA", "DR", "CTPAT", "STRA", "ENVA"],
  "Qcore": ["STS", "WCP", "SAQ"],
  "Certis": ["SABER", "GMARK", "SASO"],
}

EA_VARIANTS = ["QIMA_ETHICAL", "SMETA", "ICS", "BSCI", "RJC", "HIGG_FSLM"]
ENVA_VARIANTS = ["QIMA", "ICS", "HIGG_FEM", "BEPI", "CUSTOMIZED", "MR", "FI"]

PPSSO_BASE_URL = "https://ppsso.example.com/back-office/v2/company-profile/customer"


def build_ppsso_url(company_id: str) -> str:
  return f"{PPSSO_BASE_URL}/{company_id}"


class BookingConfig:
  def __init__(
    self,
    login_type: str,
    booking_type: str,
    product_count: int = 1,
    dry_run: bool = False,
    direct_username: str = "",
    direct_password: str = "",
    company_id: str = "",
    ppsso_url: str = "",
    ppsso_username: str = "",
    ppsso_password: str = "",
    ea_variant: Optional[str] = None,
    enva_variant: Optional[str] = None,
  ):
    self.login_type = login_type
    self.booking_type = booking_type
    self.product_count = product_count
    self.dry_run = dry_run
    self.direct_username = direct_username
    self.direct_password = direct_password
    self.company_id = company_id
    self.ppsso_url = ppsso_url or (build_ppsso_url(company_id) if company_id else "")
    self.ppsso_username = ppsso_username
    self.ppsso_password = ppsso_password
    self.ea_variant = ea_variant
    self.enva_variant = enva_variant

  def to_dict(self) -> dict:
    config: dict = {
      "bookingType": self.booking_type,
      "productCount": self.product_count,
      "loginType": self.login_type,
      "dryRun": self.dry_run,
      "directAccount": {
        "username": self.direct_username,
        "password": self.direct_password,
      },
      "ppssoBackdoor": {
        "url": self.ppsso_url,
        "backofficeUsername": self.ppsso_username,
        "backofficePassword": self.ppsso_password,
      },
    }
    if self.company_id:
      config["companyId"] = self.company_id
    if self.ea_variant:
      config["eaVariant"] = self.ea_variant
    if self.enva_variant:
      config["envaVariant"] = self.enva_variant
    return config

  def to_json(self) -> str:
    return json.dumps(self.to_dict(), indent=2)

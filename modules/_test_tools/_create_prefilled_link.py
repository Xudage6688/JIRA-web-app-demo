"""
Pre-filled Payment Link 生成工具
"""

import json
import math
import random
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any
import requests


API_ENDPOINTS: Dict[str, str] = {
  "DEV": "https://api-gateway.qcore-dev.qima.com/exchange-service/v1.0/pre-payment/links",
  "PP": "https://api-gateway.qcore-preprod.qima.com/exchange-service/v1.0/pre-payment/links",
  "PROD": "https://api-gateway.qima.com/exchange-service/v1.0/pre-payment/links",
}

DEFAULT_HEADERS: Dict[str, str] = {
  "Accept": "*/*",
  "Accept-Encoding": "gzip, deflate, br",
  "Connection": "keep-alive",
  "Content-Type": "application/json",
  "User-Agent": "PostmanRuntime-ApipostRuntime/1.1.0",
}

DEFAULT_FIELDS: Dict[str, Any] = {
  "companyName": "QIMA_DAISY_LIU_CLIENT",
  "contactEmail": "daisy.liu@qima.com",
  "contactName": "Daisy Test",
  "bu": "qima",
  "currency": "USD",
  "processingFee": 0,
  "sourceSystem": "NS",
  "customerId": "5C9B1F313EE14F95B79372F950F88165",
  "percentDiscount": 0.05,
  "remark": "Payment discount test",
}

DEFAULT_INVOICE_URL = (
  "https://yd125.oss-cn-hongkong.aliyuncs.com/QISHUI_yinyue_uia_X64_131689.zip"
)


@dataclass
class PaymentLinkRequest:
  amount: float
  payment_reference: str
  request_id: str
  start_date: int
  end_date: int
  sign: Optional[str] = None

  def to_dict(self) -> Dict[str, Any]:
    result = DEFAULT_FIELDS.copy()
    result.update({
      "amount": self.amount,
      "totalAmount": self.amount,
      "paymentReference": self.payment_reference,
      "requestId": self.request_id,
      "startDate": self.start_date,
      "endDate": self.end_date,
    })
    if self.sign:
      result["sign"] = self.sign
    return result


@dataclass
class PaymentLinkResponse:
  success: bool
  link_url: Optional[str] = None
  sign: Optional[str] = None
  error_message: Optional[str] = None
  status_code: Optional[int] = None
  request_data: Optional[Dict[str, Any]] = None


@dataclass
class InvoicePushResponse:
  """推送 invoice 的结果。"""
  success: bool
  request_id: Optional[str] = None
  original_request_id: Optional[str] = None
  sign: Optional[str] = None
  invoice_url: Optional[str] = None
  error_message: Optional[str] = None
  status_code: Optional[int] = None
  response_data: Optional[Any] = None


class PaymentLinkGenerator:
  DUMMY_SIGN = "a2f470ec5b3aa3dfcf8afd0e1e2f6492ba1216256d7360724fb4f425b6d8b56d"

  def __init__(self, environment: str = "PP"):
    env = environment.upper()
    if env not in API_ENDPOINTS:
      raise ValueError(f"不支持的环境: {env}")
    self.base_url = API_ENDPOINTS[env]
    self.environment = env
    self.session = requests.Session()
    self.session.headers.update(DEFAULT_HEADERS)

  def _generate_dynamic_fields(self, amount: Optional[float] = None, discount_days: int = 2) -> Dict[str, Any]:
    if amount is None:
      amount = 250.0
    timestamp = int(time.time())
    payment_reference = f"INV-2026-{str(timestamp)[-6:]}"
    request_id = f"NS-2026-{random.randint(100000, 999999)}"
    start_date = timestamp
    end_date = timestamp + (discount_days * 24 * 60 * 60)
    percent_discount = DEFAULT_FIELDS.get("percentDiscount", 0)
    discount_amount = round(amount * percent_discount, 2)
    return {
      "amount": amount,
      "totalAmount": amount,
      "paymentReference": payment_reference,
      "requestId": request_id,
      "startDate": start_date,
      "endDate": end_date,
      "discountAmount": discount_amount,
      "daysToAvailDiscount": discount_days,
    }

  def _generate_dynamic_fields_by_minutes(self, amount: Optional[float] = None, discount_minutes: int = 30) -> Dict[str, Any]:
    if amount is None:
      amount = 250.0
    timestamp = int(time.time())
    payment_reference = f"INV-2026-{str(timestamp)[-6:]}"
    request_id = f"NS-2026-{random.randint(100000, 999999)}"
    start_date = timestamp
    end_date = timestamp + (discount_minutes * 60)
    percent_discount = DEFAULT_FIELDS.get("percentDiscount", 0)
    discount_amount = round(amount * percent_discount, 2)
    days_to_avail = max(1, math.ceil(discount_minutes / 1440))
    return {
      "amount": amount,
      "totalAmount": amount,
      "paymentReference": payment_reference,
      "requestId": request_id,
      "startDate": start_date,
      "endDate": end_date,
      "discountAmount": discount_amount,
      "daysToAvailDiscount": days_to_avail,
    }

  def _generate_expired_dynamic_fields(self, amount: Optional[float] = None, expired_minutes: int = 10) -> Dict[str, Any]:
    if amount is None:
      amount = 250.0
    timestamp = int(time.time())
    payment_reference = f"INV-2026-{str(timestamp)[-6:]}"
    request_id = f"NS-2026-{random.randint(100000, 999999)}"
    start_date = timestamp - ((expired_minutes + 1) * 60)
    end_date = timestamp - (expired_minutes * 60)
    percent_discount = DEFAULT_FIELDS.get("percentDiscount", 0)
    discount_amount = round(amount * percent_discount, 2)
    return {
      "amount": amount,
      "totalAmount": amount,
      "paymentReference": payment_reference,
      "requestId": request_id,
      "startDate": start_date,
      "endDate": end_date,
      "discountAmount": discount_amount,
      "daysToAvailDiscount": 1,
    }

  def _generate_pending_dynamic_fields(self, amount: Optional[float] = None, pending_minutes: int = 5, discount_duration_minutes: int = 60) -> Dict[str, Any]:
    if amount is None:
      amount = 250.0
    timestamp = int(time.time())
    payment_reference = f"INV-2026-{str(timestamp)[-6:]}"
    request_id = f"NS-2026-{random.randint(100000, 999999)}"
    start_date = timestamp + (pending_minutes * 60)
    end_date = start_date + (discount_duration_minutes * 60)
    percent_discount = DEFAULT_FIELDS.get("percentDiscount", 0)
    discount_amount = round(amount * percent_discount, 2)
    days_to_avail = max(1, math.ceil(discount_duration_minutes / 1440))
    return {
      "amount": amount,
      "totalAmount": amount,
      "paymentReference": payment_reference,
      "requestId": request_id,
      "startDate": start_date,
      "endDate": end_date,
      "discountAmount": discount_amount,
      "daysToAvailDiscount": days_to_avail,
    }

  def step1_create_initial_request(self, dynamic_fields: Dict[str, Any]) -> Dict[str, Any]:
    request_data = DEFAULT_FIELDS.copy()
    request_data.update(dynamic_fields)
    request_data["sign"] = self.DUMMY_SIGN
    try:
      response = self.session.post(self.base_url, json=request_data, timeout=30)
      if response.status_code == 200:
        result = response.json()
        sign = None
        if result.get("success"):
          data = result.get("data", {})
          if isinstance(data, dict):
            sign = data.get("sign")
          elif isinstance(data, str):
            sign = data
        if not sign and "Expected:" in result.get("message", ""):
          match = re.search(r'Expected:\s*([a-f0-9]{64})', result.get("message", ""))
          if match:
            sign = match.group(1)
        if sign:
          return {"success": True, "sign": sign, "response": result, "request_data": request_data}
      return {"success": False, "error": "响应中未找到sign", "response": response.text if hasattr(response, 'text') else str(response)}
    except Exception as e:
      return {"success": False, "error": str(e)}

  def step2_submit_with_sign(self, request_data: Dict[str, Any], sign: str) -> PaymentLinkResponse:
    request_data["sign"] = sign
    try:
      response = self.session.post(self.base_url, json=request_data, timeout=30)
      if response.status_code == 200:
        result = response.json()
        data = result.get("data", {})
        payment_link = data.get("paymentLink", {}) if isinstance(data, dict) else {}
        link_url = (
          payment_link.get("link")
          or data.get("linkUrl")
          or data.get("link_url")
          or data.get("url")
          or result.get("linkUrl")
          or result.get("link_url")
          or result.get("url")
        )
        return PaymentLinkResponse(
          success=True, link_url=link_url, sign=sign,
          request_data=request_data,
        )
      return PaymentLinkResponse(
        success=False, error_message=response.text, status_code=response.status_code,
      )
    except Exception as e:
      return PaymentLinkResponse(success=False, error_message=str(e))

  def generate_link(self, amount: Optional[float] = None, discount_days: int = 2) -> PaymentLinkResponse:
    try:
      dynamic_fields = self._generate_dynamic_fields(amount, discount_days)
      step1_result = self.step1_create_initial_request(dynamic_fields)
      if not step1_result.get("success"):
        return PaymentLinkResponse(success=False, error_message=step1_result.get("error"))
      sign = step1_result["sign"]
      request_data = step1_result["request_data"]
      return self.step2_submit_with_sign(request_data, sign)
    except Exception as e:
      return PaymentLinkResponse(success=False, error_message=str(e))

  def generate_random_link(self, discount_days: int = 2) -> PaymentLinkResponse:
    amount = round(random.uniform(0.01, 10000), 2)
    return self.generate_link(amount, discount_days)

  def generate_link_by_minutes(self, amount: Optional[float] = None, discount_minutes: int = 30) -> PaymentLinkResponse:
    try:
      dynamic_fields = self._generate_dynamic_fields_by_minutes(amount, discount_minutes)
      step1_result = self.step1_create_initial_request(dynamic_fields)
      if not step1_result.get("success"):
        return PaymentLinkResponse(success=False, error_message=step1_result.get("error"))
      sign = step1_result["sign"]
      request_data = step1_result["request_data"]
      return self.step2_submit_with_sign(request_data, sign)
    except Exception as e:
      return PaymentLinkResponse(success=False, error_message=str(e))

  def generate_expired_link(self, amount: Optional[float] = None, expired_minutes: int = 5) -> PaymentLinkResponse:
    try:
      dynamic_fields = self._generate_expired_dynamic_fields(amount, expired_minutes)
      step1_result = self.step1_create_initial_request(dynamic_fields)
      if not step1_result.get("success"):
        return PaymentLinkResponse(success=False, error_message=step1_result.get("error"))
      sign = step1_result["sign"]
      request_data = step1_result["request_data"]
      return self.step2_submit_with_sign(request_data, sign)
    except Exception as e:
      return PaymentLinkResponse(success=False, error_message=str(e))

  def generate_pending_link(self, amount: Optional[float] = None, pending_minutes: int = 5, discount_duration_minutes: int = 60) -> PaymentLinkResponse:
    try:
      dynamic_fields = self._generate_pending_dynamic_fields(amount, pending_minutes, discount_duration_minutes)
      step1_result = self.step1_create_initial_request(dynamic_fields)
      if not step1_result.get("success"):
        return PaymentLinkResponse(success=False, error_message=step1_result.get("error"))
      sign = step1_result["sign"]
      request_data = step1_result["request_data"]
      return self.step2_submit_with_sign(request_data, sign)
    except Exception as e:
      return PaymentLinkResponse(success=False, error_message=str(e))

  def _new_request_id(self) -> str:
    """生成本次推送用的随机 requestId。"""
    return f"NS-2026-{random.randint(100000, 999999)}"

  def _invoice_endpoint(self, request_id: str, original_request_id: str, sign: str) -> str:
    """组装推送 invoice 的 PUT URL。"""
    return (
      f"{self.base_url}/invoice"
      f"?requestId={request_id}"
      f"&originalRequestId={original_request_id}"
      f"&sign={sign}"
    )

  def _extract_sign(self, result: Dict[str, Any]) -> Optional[str]:
    """从 API 响应中提取 sign（data.sign 或 message 中的 Expected）。"""
    sign = None
    if result.get("success"):
      data = result.get("data", {})
      if isinstance(data, dict):
        sign = data.get("sign")
      elif isinstance(data, str):
        sign = data
    if not sign and "Expected:" in result.get("message", ""):
      match = re.search(r"Expected:\s*([a-f0-9]{64})", result.get("message", ""))
      if match:
        sign = match.group(1)
    return sign

  def step1_fetch_invoice_sign(
    self,
    request_id: str,
    original_request_id: str,
    invoice_url: str,
  ) -> Dict[str, Any]:
    """第一步：用 dummy sign 调用 invoice PUT，解析真实 sign。"""
    url = self._invoice_endpoint(request_id, original_request_id, self.DUMMY_SIGN)
    body = {"invoiceUrl": invoice_url}
    try:
      response = self.session.put(url, json=body, timeout=30)
      if response.status_code == 200:
        result = response.json()
        sign = self._extract_sign(result)
        if sign:
          return {"success": True, "sign": sign, "response": result}
        return {
          "success": False,
          "error": "响应中未找到sign",
          "response": result,
        }
      return {
        "success": False,
        "error": response.text,
        "status_code": response.status_code,
      }
    except Exception as e:
      return {"success": False, "error": str(e)}

  def step2_push_invoice_with_sign(
    self,
    request_id: str,
    original_request_id: str,
    invoice_url: str,
    sign: str,
  ) -> InvoicePushResponse:
    """第二步：用真实 sign 推送 invoice。"""
    url = self._invoice_endpoint(request_id, original_request_id, sign)
    body = {"invoiceUrl": invoice_url}
    try:
      response = self.session.put(url, json=body, timeout=30)
      if response.status_code == 200:
        try:
          result = response.json()
        except Exception:
          result = response.text
        return InvoicePushResponse(
          success=True,
          request_id=request_id,
          original_request_id=original_request_id,
          sign=sign,
          invoice_url=invoice_url,
          status_code=response.status_code,
          response_data=result,
        )
      return InvoicePushResponse(
        success=False,
        request_id=request_id,
        original_request_id=original_request_id,
        invoice_url=invoice_url,
        error_message=response.text,
        status_code=response.status_code,
      )
    except Exception as e:
      return InvoicePushResponse(
        success=False,
        request_id=request_id,
        original_request_id=original_request_id,
        invoice_url=invoice_url,
        error_message=str(e),
      )

  def push_invoice(
    self,
    original_request_id: str,
    invoice_url: Optional[str] = None,
    request_id: Optional[str] = None,
  ) -> InvoicePushResponse:
    """两步流程推送 invoice：先取 sign，再正式 PUT。"""
    if not original_request_id or not original_request_id.strip():
      return InvoicePushResponse(
        success=False, error_message="originalRequestId 不能为空"
      )
    invoice_url = invoice_url or DEFAULT_INVOICE_URL
    request_id = request_id or self._new_request_id()
    try:
      step1 = self.step1_fetch_invoice_sign(
        request_id, original_request_id.strip(), invoice_url
      )
      if not step1.get("success"):
        return InvoicePushResponse(
          success=False,
          request_id=request_id,
          original_request_id=original_request_id.strip(),
          invoice_url=invoice_url,
          error_message=step1.get("error"),
          status_code=step1.get("status_code"),
          response_data=step1.get("response"),
        )
      return self.step2_push_invoice_with_sign(
        request_id,
        original_request_id.strip(),
        invoice_url,
        step1["sign"],
      )
    except Exception as e:
      return InvoicePushResponse(
        success=False,
        request_id=request_id,
        original_request_id=original_request_id.strip(),
        invoice_url=invoice_url,
        error_message=str(e),
      )

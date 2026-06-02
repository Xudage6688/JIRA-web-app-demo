"""
SHEIN 订单流程测试
"""

import json
import time
import urllib.request
from datetime import datetime
from typing import Optional, List, Tuple


class SheinOrderFlow:
  def __init__(self):
    ts = str(int(time.time()))[:8]
    self.ref_num = f"TR250{ts}"
    self.user_id = "369A2C205AA54300A84006CB096EF95B"
    self.lt_ref_num: Optional[str] = None
    self.lt_ref_id: Optional[str] = None
    self.base_url = "https://api-gateway.qcore-preprod.example.com"

  def log(self, message: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"

  def step1_2_mock_shein_booking_request(self) -> bool:
    url = f"{self.base_url}/exchange-service/v1.0/shein/mock/order-info/source-api-data?refNum={self.ref_num}"
    payload = {
      "code": 0,
      "info": {
        "sheinNo": self.ref_num,
        "sourceSystem": 2,
        "sourceSystemName": "FSP",
        "supplierId": "8749",
        "supplierModQcTypeCode": "CPC Testing",
        "supplierModQcTypeName": "CPC送检",
        "supplierName": "成铭五金辅料",
        "applyInfo": {
          "address": "广州市海珠区康乐西约大街15号成铭五金",
          "applyUserName": "成铭五金1号",
          "contactNum": "13719255725",
          "email": "724610984@qq.com",
        },
        "sampleInfoList": [
          {"ageGroup": "婴幼儿（0-3）", "sampleNo": "F00500001", "sampleNoType": 1},
          {"ageGroup": "婴幼儿（0-3）", "sampleNo": "F00500002", "sampleNoType": 1},
          {"ageGroup": "婴幼儿（0-3）", "sampleNo": "F00500003", "sampleNoType": 1},
        ],
        "checkTypeCode": "Textile Classification",
        "checkTypeName": "纺织品",
      },
      "msg": "success",
    }
    try:
      data = json.dumps(payload).encode("utf-8")
      headers = {"Content-Type": "application/json"}
      req = urllib.request.Request(url, data=data, headers=headers, method="POST")
      with urllib.request.urlopen(req) as response:
        response_text = response.read().decode("utf-8")
        response_data = json.loads(response_text)
        if response_data.get("code") == 200 and response_data.get("message") == "mock shein order info data success":
          return True
        return False
    except Exception:
      return False

  def step3_4_process_booking_request(self) -> bool:
    url = f"{self.base_url}/exchange-service/v1.0/shein/booking?refNum={self.ref_num}&userId={self.user_id}&isCache=true"
    try:
      headers = {
        "X-Kong-Request-Id": "6332705931cba414ed1cc84ece081f3c",
        "Content-Type": "application/json",
      }
      req = urllib.request.Request(url, data=None, headers=headers, method="POST")
      with urllib.request.urlopen(req) as response:
        response_text = response.read().decode("utf-8")
        response_data = json.loads(response_text)
        if response_data.get("code") == 0 and "data" in response_data:
          data = response_data["data"]
          self.lt_ref_num = data.get("ltRefNum")
          self.lt_ref_id = data.get("ltRefId")
          return True
        return False
    except Exception:
      return False

  def run_all_steps(self) -> Tuple[bool, List[str]]:
    logs = []
    logs.append(self.log("开始SHEIN订单流程测试"))
    if not self.step1_2_mock_shein_booking_request():
      logs.append(self.log("测试中断: 步骤1-2失败"))
      return False, logs
    if not self.step3_4_process_booking_request():
      logs.append(self.log("测试中断: 步骤3-4失败"))
      return False, logs
    logs.append(self.log("SHEIN订单流程测试完成"))
    return True, logs

  def run_all_steps_original(self) -> bool:
    if not self.step1_2_mock_shein_booking_request():
      return False
    if not self.step3_4_process_booking_request():
      return False
    return True

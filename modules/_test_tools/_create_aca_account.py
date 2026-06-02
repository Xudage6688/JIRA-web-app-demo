"""
ACA 测试账号创建工具
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional
from urllib.parse import quote
import requests


API_ENDPOINTS: Dict[str, str] = {
  "DEV": "http://devservices.example.com/customer-service/customer-legacy/create-new-account",
  "PP": "https://api-gateway.qcore-preprod.example.com/customer-service/customer-legacy/create-new-account",
}


DEFAULT_FIELDS: Dict[str, str] = {
  "domain-name": "China",
  "country": "China",
  "firstname": "Test",
  "lastname": "User",
  "city": "Shenzhen",
  "industry": "Eyewear",
  "address": "Shenzhen",
  "mobile": "+86 571 8659 3800",
  "telephone": "+86 571 8659 3800",
  "fax": "+86 571 8659 3800",
  "post-code": "518001",
  "BU": "AI",
  "billing-salutation": "Mr",
  "billing-email": "qateam@example.com",
  "billing-contact-name": "QA",
  "position": "QA",
  "salutation": "Mr",
  "turnover": "0",
  "is-food-inspection": "false",
  "is-chb": "false",
  "is-test-account": "false",
  "home-page": "",
  "activity": "",
  "affiliate-id": "",
  "user-ip": "",
  "supplier-company-name": "",
  "refer": "",
}


@dataclass
class AccountInfo:
  login: str
  emails: str
  password: str
  company_name: str

  def to_dict(self) -> Dict:
    base = DEFAULT_FIELDS.copy()
    base.update({
      "login": self.login,
      "emails": self.emails,
      "password": self.password,
      "company-name": self.company_name,
    })
    return base


def create_aca_account(account_info: AccountInfo, environment: str = "PP") -> Dict:
  env = environment.upper()
  if env not in API_ENDPOINTS:
    return {"success": False, "error": f"不支持的环境: {env}，请使用 DEV 或 PP"}

  base_url = API_ENDPOINTS[env]
  client_info_dict = account_info.to_dict()
  client_info_json = json.dumps(client_info_dict, ensure_ascii=False)
  encoded = quote(client_info_json, safe='')
  encoded = encoded.replace("'", "%27").replace('"', "%22")
  url = f"{base_url}?clientInfo={encoded}"

  try:
    response = requests.post(url, timeout=30)
    if response.status_code == 200:
      try:
        data = response.json()
        return {
          "success": True, "status_code": response.status_code, "data": data,
          "account_info": {
            "login": account_info.login, "email": account_info.emails,
            "password": account_info.password, "company": account_info.company_name,
            "environment": env,
          },
        }
      except json.JSONDecodeError:
        return {"success": True, "status_code": response.status_code, "raw_response": response.text}
    else:
      return {"success": False, "status_code": response.status_code, "error": response.text}
  except requests.exceptions.Timeout:
    return {"success": False, "error": "请求超时，请检查网络连接"}
  except requests.exceptions.ConnectionError:
    return {"success": False, "error": "无法连接到服务器，请检查网络或 VPN 连接"}
  except requests.exceptions.RequestException as e:
    return {"success": False, "error": str(e)}
  except Exception as e:
    return {"success": False, "error": str(e)}

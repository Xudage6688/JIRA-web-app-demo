import pytest
import json
from modules._test_tools._create_aca_account import create_aca_account, AccountInfo, API_ENDPOINTS


class TestCreateAcaAccount:
  def testSuccess(self, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.json.return_value = {"companyId": 123, "status": "ACTIVE"}
    mocker.patch('requests.post', return_value=mockResponse)

    info = AccountInfo(login="testuser", emails="test@qima.com", password="Test123", company_name="TestCo")
    result = create_aca_account(info, "PP")
    assert result["success"] is True
    assert result["data"]["companyId"] == 123

  def testApiFailure(self, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 400
    mockResponse.text = "Bad Request"
    mocker.patch('requests.post', return_value=mockResponse)

    info = AccountInfo(login="testuser", emails="test@qima.com", password="Test123", company_name="TestCo")
    result = create_aca_account(info, "PP")
    assert result["success"] is False

  def testTimeout(self, mocker):
    mocker.patch('requests.post', side_effect=Exception("timeout"))
    info = AccountInfo(login="testuser", emails="test@qima.com", password="Test123", company_name="TestCo")
    result = create_aca_account(info, "PP")
    assert result["success"] is False

  def testInvalidEnv(self):
    info = AccountInfo(login="testuser", emails="test@qima.com", password="Test123", company_name="TestCo")
    result = create_aca_account(info, "INVALID")
    assert result["success"] is False
    assert "不支持" in result["error"]

  def testAccountInfoToDict(self):
    info = AccountInfo(login="testuser", emails="test@qima.com", password="Test123", company_name="TestCo")
    d = info.to_dict()
    assert d["login"] == "testuser"
    assert d["emails"] == "test@qima.com"
    assert d["password"] == "Test123"
    assert d["company-name"] == "TestCo"
    assert "domain-name" in d

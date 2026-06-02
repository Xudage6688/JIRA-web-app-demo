import time
import math
import pytest
from modules._test_tools._create_prefilled_link import (
  PaymentLinkGenerator, PaymentLinkResponse, DEFAULT_FIELDS,
)


class TestPaymentLinkGenerator:
  @pytest.fixture
  def generator(self):
    return PaymentLinkGenerator(environment="PP")

  def _mock_steps(self, generator, mocker, link_url="https://pay.example.com/link/abc"):
    step1Result = {"success": True, "sign": "sign123", "request_data": {"amount": 250}}
    mocker.patch.object(generator, 'step1_create_initial_request', return_value=step1Result)
    mocker.patch.object(generator, 'step2_submit_with_sign', return_value=PaymentLinkResponse(
      success=True, link_url=link_url, sign="sign123",
    ))

  # ── 基本链路 ──

  def testGenerateLink(self, generator, mocker):
    self._mock_steps(generator, mocker)
    result = generator.generate_link(amount=250, discount_days=2)
    assert result.success is True
    assert "pay.example.com" in result.link_url

  def testGenerateLinkFailure(self, generator, mocker):
    mocker.patch.object(generator, 'step1_create_initial_request', return_value={"success": False, "error": "no sign"})
    result = generator.generate_link(amount=250, discount_days=2)
    assert result.success is False

  def testGenerateRandomLink(self, generator, mocker):
    self._mock_steps(generator, mocker, link_url="https://pay.example.com/link/random")
    result = generator.generate_random_link(discount_days=2)
    assert result.success is True

  def testInvalidEnvironment(self):
    with pytest.raises(ValueError):
      PaymentLinkGenerator(environment="INVALID")

  # ── 已过期场景 ──

  def testGenerateExpiredLink(self, generator, mocker):
    self._mock_steps(generator, mocker, link_url="https://pay.example.com/link/expired")
    result = generator.generate_expired_link(amount=250, expired_minutes=5)
    assert result.success is True

  def testExpiredDynamicFieldsEndDateInPast(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_expired_dynamic_fields(amount=250, expired_minutes=5)
    now = int(time.time())
    assert fields["endDate"] < now, "过期链接的 endDate 应在当前时间之前"
    assert fields["startDate"] < fields["endDate"]
    assert fields["amount"] == 250
    assert fields["daysToAvailDiscount"] == 1

  # ── 待生效场景 ──

  def testGeneratePendingLink(self, generator, mocker):
    self._mock_steps(generator, mocker, link_url="https://pay.example.com/link/pending")
    result = generator.generate_pending_link(amount=250, pending_minutes=10, discount_duration_minutes=120)
    assert result.success is True

  def testPendingDynamicFieldsStartDateInFuture(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_pending_dynamic_fields(amount=500, pending_minutes=10, discount_duration_minutes=60)
    now = int(time.time())
    assert fields["startDate"] > now, "待生效链接的 startDate 应在当前时间之后"
    assert fields["endDate"] > fields["startDate"]
    assert fields["amount"] == 500

  # ── 分钟精度场景 ──

  def testGenerateLinkByMinutes(self, generator, mocker):
    self._mock_steps(generator, mocker, link_url="https://pay.example.com/link/bymin")
    result = generator.generate_link_by_minutes(amount=250, discount_minutes=30)
    assert result.success is True

  def testMinutesDynamicFields(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_dynamic_fields_by_minutes(amount=100, discount_minutes=45)
    now = int(time.time())
    assert fields["endDate"] == fields["startDate"] + 45 * 60
    assert fields["amount"] == 100
    expected_days = max(1, math.ceil(45 / 1440))
    assert fields["daysToAvailDiscount"] == expected_days

  # ── 金额边界场景 ──

  def testGenerateLinkMinAmount(self, generator, mocker):
    self._mock_steps(generator, mocker)
    result = generator.generate_link(amount=0.01, discount_days=1)
    assert result.success is True

  def testGenerateLinkMaxAmount(self, generator, mocker):
    self._mock_steps(generator, mocker)
    result = generator.generate_link(amount=10000, discount_days=30)
    assert result.success is True

  def testDynamicFieldsMinAmount(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_dynamic_fields(amount=0.01, discount_days=1)
    assert fields["amount"] == 0.01
    assert fields["totalAmount"] == 0.01

  def testDynamicFieldsMaxAmount(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_dynamic_fields(amount=10000, discount_days=365)
    assert fields["amount"] == 10000
    assert fields["totalAmount"] == 10000
    assert fields["daysToAvailDiscount"] == 365

  # ── 零折扣场景 ──

  def testGenerateLinkZeroDiscount(self, generator, mocker):
    self._mock_steps(generator, mocker)
    result = generator.generate_link(amount=250, discount_days=0)
    assert result.success is True

  def testDynamicFieldsZeroDays(self):
    gen = PaymentLinkGenerator("PP")
    fields = gen._generate_dynamic_fields(amount=250, discount_days=0)
    now = int(time.time())
    assert fields["endDate"] == now, "折扣天数为0时 endDate 应等于 startDate"
    assert fields["daysToAvailDiscount"] == 0
    assert fields["discountAmount"] == round(250 * DEFAULT_FIELDS["percentDiscount"], 2)

  # ── 多 BU 场景 ──

  def testGenerateLinkWithDifferentBU(self, generator, mocker):
    import modules._test_tools._create_prefilled_link as mod
    originalBu = mod.DEFAULT_FIELDS["bu"]
    try:
      mod.DEFAULT_FIELDS["bu"] = "qimawqs"
      self._mock_steps(generator, mocker)
      result = generator.generate_link(amount=250)
      assert result.success is True
    finally:
      mod.DEFAULT_FIELDS["bu"] = originalBu

  def testGenerateLinkWithQimaCertisBU(self, generator, mocker):
    import modules._test_tools._create_prefilled_link as mod
    originalBu = mod.DEFAULT_FIELDS["bu"]
    try:
      mod.DEFAULT_FIELDS["bu"] = "qimacertis"
      self._mock_steps(generator, mocker)
      result = generator.generate_link(amount=250)
      assert result.success is True
    finally:
      mod.DEFAULT_FIELDS["bu"] = originalBu

  # ── 多币种场景 ──

  def testGenerateLinkWithEUR(self, generator, mocker):
    import modules._test_tools._create_prefilled_link as mod
    originalCurrency = mod.DEFAULT_FIELDS["currency"]
    try:
      mod.DEFAULT_FIELDS["currency"] = "EUR"
      self._mock_steps(generator, mocker)
      result = generator.generate_link(amount=250)
      assert result.success is True
    finally:
      mod.DEFAULT_FIELDS["currency"] = originalCurrency

  def testGenerateLinkWithMXN(self, generator, mocker):
    import modules._test_tools._create_prefilled_link as mod
    originalCurrency = mod.DEFAULT_FIELDS["currency"]
    try:
      mod.DEFAULT_FIELDS["currency"] = "MXN"
      self._mock_steps(generator, mocker)
      result = generator.generate_link(amount=250)
      assert result.success is True
    finally:
      mod.DEFAULT_FIELDS["currency"] = originalCurrency

  # ── sign / URL 提取 ──

  def testStep1ExtractSignFromExpected(self, generator, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.json.return_value = {
      "success": False,
      "message": "Sign validation failed. Expected: a2f470ec5b3aa3dfcf8afd0e1e2f6492ba1216256d7360724fb4f425b6d8b56d",
    }
    mocker.patch.object(generator.session, 'post', return_value=mockResponse)

    dynamic_fields = {
      "amount": 250, "totalAmount": 250,
      "paymentReference": "INV-2026-123456", "requestId": "NS-2026-123456",
      "startDate": 0, "endDate": 86400,
    }
    result = generator.step1_create_initial_request(dynamic_fields)
    assert result["success"] is True
    assert result["sign"] == "a2f470ec5b3aa3dfcf8afd0e1e2f6492ba1216256d7360724fb4f425b6d8b56d"

  def testStep2ExtractLinkUrl(self, generator, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.json.return_value = {
      "success": True,
      "data": {
        "paymentLink": {"link": "https://pay.qima.com/link/test123"},
      },
    }
    mocker.patch.object(generator.session, 'post', return_value=mockResponse)

    result = generator.step2_submit_with_sign({"amount": 250}, "sign123")
    assert result.success is True
    assert result.link_url == "https://pay.qima.com/link/test123"

  def testStep2ExtractLinkUrlAlternativeField(self, generator, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.json.return_value = {
      "success": True,
      "data": {"linkUrl": "https://pay.qima.com/link/alt"},
    }
    mocker.patch.object(generator.session, 'post', return_value=mockResponse)

    result = generator.step2_submit_with_sign({"amount": 250}, "sign456")
    assert result.success is True
    assert result.link_url == "https://pay.qima.com/link/alt"

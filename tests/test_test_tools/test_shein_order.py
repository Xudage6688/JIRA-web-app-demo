import pytest
from modules._test_tools._shein_order import SheinOrderFlow


class TestSheinOrderFlow:
  @pytest.fixture
  def flow(self):
    return SheinOrderFlow()

  def testInit(self, flow):
    assert flow.ref_num.startswith("TR250")
    assert flow.user_id == "369A2C205AA54300A84006CB096EF95B"
    assert "qcore-preprod" in flow.base_url

  def testStep1Success(self, flow, mocker):
    mockResponse = mocker.MagicMock()
    mockResponse.read.return_value = b'{"code": 200, "message": "mock shein order info data success"}'
    mockResponse.__enter__.return_value = mockResponse
    mocker.patch('urllib.request.urlopen', return_value=mockResponse)

    result = flow.step1_2_mock_shein_booking_request()
    assert result is True

  def testStep1Failure(self, flow, mocker):
    mockResponse = mocker.MagicMock()
    mockResponse.read.return_value = b'{"code": 500, "message": "error"}'
    mockResponse.__enter__.return_value = mockResponse
    mocker.patch('urllib.request.urlopen', return_value=mockResponse)

    result = flow.step1_2_mock_shein_booking_request()
    assert result is False

  def testStep3Success(self, flow, mocker):
    mockResponse = mocker.MagicMock()
    mockResponse.read.return_value = (
      b'{"code": 0, "message": "SUCCESS", '
      b'"data": {"refNum": "TR25012345678", "ltRefNum": "LT250001", "ltRefId": "12345"}}'
    )
    mockResponse.__enter__.return_value = mockResponse
    mocker.patch('urllib.request.urlopen', return_value=mockResponse)

    flow.ref_num = "TR25012345678"
    result = flow.step3_4_process_booking_request()
    assert result is True
    assert flow.lt_ref_num == "LT250001"

  def testRunAllSteps(self, flow, mocker):
    mockStep1 = mocker.patch.object(flow, 'step1_2_mock_shein_booking_request', return_value=True)
    mockStep3 = mocker.patch.object(flow, 'step3_4_process_booking_request', return_value=True)

    result = flow.run_all_steps_original()
    assert result is True
    mockStep1.assert_called_once()
    mockStep3.assert_called_once()

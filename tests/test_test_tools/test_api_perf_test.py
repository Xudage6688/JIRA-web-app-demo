import pytest
from modules._test_tools._api_perf_test import (
  TestConfig, TestReport, RequestResult,
  APIPerformanceTester, parse_curl_command,
)


class TestTestConfig:
  def testDefaultValues(self):
    config = TestConfig(url="http://example.com")
    assert config.method == "GET"
    assert config.concurrent_users == 10
    assert config.total_requests == 100
    assert config.timeout == 30
    assert config.test_mode == "requests"


class TestAPIPerformanceTester:
  @pytest.fixture
  def config(self):
    return TestConfig(url="http://test.api/data", method="GET")

  @pytest.fixture
  def tester(self, config):
    return APIPerformanceTester(config)

  def testSingleRequestSyncSuccess(self, tester, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.content = b'{"ok": true}'
    mocker.patch.object(tester.session, 'get', return_value=mockResponse)

    result = tester.single_request_sync()
    assert result.success is True
    assert result.status_code == 200

  def testSingleRequestSyncFailure(self, tester, mocker):
    mocker.patch.object(tester.session, 'get', side_effect=Exception("connection error"))

    result = tester.single_request_sync()
    assert result.success is False
    assert "connection error" in result.error_message

  def testGenerateReport(self, tester):
    results = []
    for i in range(20):
      results.append(RequestResult(success=True, response_time=0.1 * (i + 1), status_code=200, response_size=100))
    results.append(RequestResult(success=False, response_time=0.3, status_code=500, response_size=0, error_message="server error"))
    results.append(RequestResult(success=False, response_time=0.4, status_code=0, response_size=0, error_message="timeout error"))
    report = tester.generate_report(results)
    assert report.total_requests == 22
    assert report.successful_requests == 20
    assert report.failed_requests == 2
    assert report.success_rate == pytest.approx(90.9, rel=0.1)
    # sorted times: [0.1, 0.2, ..., 2.0], n=20
    # p75 = sorted_times[int(20*0.75)] = sorted_times[15] = 1.6
    # p90 = sorted_times[int(20*0.90)] = sorted_times[18] = 1.9
    # p95 = sorted_times[int(20*0.95)] = sorted_times[19] = 2.0
    # p99 = sorted_times[int(20*0.99)] = sorted_times[19] = 2.0
    assert report.p75_response_time == pytest.approx(1.6, rel=0.1)
    assert report.p90_response_time == pytest.approx(1.9, rel=0.1)
    assert report.p95_response_time == pytest.approx(2.0, rel=0.1)
    assert report.p99_response_time == pytest.approx(2.0, rel=0.1)
    assert report.std_dev_response_time > 0
    # status code distribution
    assert report.status_code_distribution == {200: 20, 500: 1, 0: 1}
    # error distribution
    assert report.error_distribution.get("timeout") == 1

  def testRunSyncTest(self, tester, mocker):
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.content = b'ok'
    mocker.patch.object(tester.session, 'get', return_value=mockResponse)

    results = tester.run_sync_test()
    assert len(results) == 100

  def testRunSyncTestWithRemainder(self, mocker):
    # total_requests=101, concurrent_users=10 → should make 101 requests
    config = TestConfig(url="http://test.api/data", total_requests=101, concurrent_users=10)
    tester = APIPerformanceTester(config)
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.content = b'ok'
    mocker.patch.object(tester.session, 'get', return_value=mockResponse)

    results = tester.run_sync_test()
    assert len(results) == 101

  def testRunSyncTestWithRemainder2(self, mocker):
    # total_requests=50, concurrent_users=20 → 50//20=2 each, remainder=10, total=20*2+10=50
    config = TestConfig(url="http://test.api/data", total_requests=50, concurrent_users=20)
    tester = APIPerformanceTester(config)
    mockResponse = mocker.Mock()
    mockResponse.status_code = 200
    mockResponse.content = b'ok'
    mocker.patch.object(tester.session, 'get', return_value=mockResponse)

    results = tester.run_sync_test()
    assert len(results) == 50


class TestParseCurlCommand:
  def testParseBasicCurl(self):
    curl = """curl --location 'https://api.example.com/data?id=1' --header 'Auth: token123'"""
    config = parse_curl_command(curl)
    assert config.url == "https://api.example.com/data"
    assert config.headers == {"Auth": "token123"}

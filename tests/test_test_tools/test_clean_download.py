import pytest
import tempfile
from pathlib import Path
from modules._test_tools._clean_download import clean_download_files, format_size


class TestCleanDownloadFiles:
  @pytest.fixture
  def tempDir(self):
    with tempfile.TemporaryDirectory() as tmp:
      (Path(tmp) / "test.exe").write_text("exe content")
      (Path(tmp) / "test.zip").write_text("zip content")
      (Path(tmp) / "test.jpg").write_text("jpg content")
      (Path(tmp) / "important.doc").write_text("doc content")
      yield tmp

  def testCleanSpecificExtensions(self, tempDir):
    result = clean_download_files(tempDir, ["exe", "zip"])
    assert result["deleted_count"] == 2
    assert result["failed_count"] == 0

  def testCleanAllExtensions(self, tempDir):
    result = clean_download_files(tempDir, ["exe", "zip", "jpg"])
    assert result["deleted_count"] == 3

  def testNoMatchingFiles(self, tempDir):
    result = clean_download_files(tempDir, ["pdf"])
    assert result["deleted_count"] == 0

  def testCaseInsensitive(self, tempDir):
    (Path(tempDir) / "test.EXE").write_text("exe uppercase")
    result = clean_download_files(tempDir, ["exe"])
    assert result["deleted_count"] >= 1


class TestFormatSize:
  def testBytes(self):
    assert "500.00 B" in format_size(500)

  def testKB(self):
    assert "KB" in format_size(2048)

  def testMB(self):
    assert "MB" in format_size(1048576 * 5)

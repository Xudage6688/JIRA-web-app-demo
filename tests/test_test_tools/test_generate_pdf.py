import pytest
import tempfile
from pathlib import Path
from modules._test_tools._generate_pdf import generate_minimal_pdf


class TestGenerateMinimalPdf:
  @pytest.fixture
  def tempDir(self):
    with tempfile.TemporaryDirectory() as tmp:
      yield tmp

  def testGenerateSingleFile(self, tempDir):
    files = generate_minimal_pdf(target_size_mb=1, file_count=1, output_dir=tempDir)
    assert len(files) == 1
    assert Path(files[0]).exists()
    size_mb = Path(files[0]).stat().st_size / (1024 * 1024)
    assert 0.5 <= size_mb <= 2.0

  def testGenerateMultipleFiles(self, tempDir):
    files = generate_minimal_pdf(target_size_mb=1, file_count=3, output_dir=tempDir)
    assert len(files) == 3
    for f in files:
      assert Path(f).exists()

  def testOutputDirCreated(self, tempDir):
    output = Path(tempDir) / "pdf_output"
    files = generate_minimal_pdf(target_size_mb=1, file_count=1, output_dir=str(output))
    assert output.exists()
    assert len(files) == 1

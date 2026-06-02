import pytest
import tempfile
from pathlib import Path
from modules._test_tools._generate_photo import generate_random_photos, generate_number_photos


class TestGeneratePhoto:
  @pytest.fixture
  def tempDir(self):
    with tempfile.TemporaryDirectory() as tmp:
      yield tmp

  def testGenerateRandomPhotos(self, tempDir):
    files = generate_random_photos(num_photos=2, width=10, height=10, output_dir=tempDir)
    assert len(files) == 2
    for f in files:
      assert Path(f).exists()
      assert Path(f).stat().st_size > 0

  def testGenerateNumberPhotos(self, tempDir):
    files = generate_number_photos(num_photos=2, width=10, height=10, output_dir=tempDir)
    assert len(files) == 2
    for f in files:
      assert Path(f).exists()

  def testOutputDirCreated(self, tempDir):
    output = Path(tempDir) / "photos"
    files = generate_random_photos(num_photos=1, width=10, height=10, output_dir=str(output))
    assert output.exists()
    assert len(files) == 1

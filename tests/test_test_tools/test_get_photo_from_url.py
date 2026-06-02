import pytest
from modules._test_tools._get_photo_from_url import TESLA_MODEL_MAP, get_model_zip_url, download_tesla_images


class TestGetPhotoFromUrl:
  def testModelMapHasEntries(self):
    assert len(TESLA_MODEL_MAP) > 0
    assert "cybercab" in TESLA_MODEL_MAP

  def testGetModelZipUrlFound(self):
    url = get_model_zip_url("cybercab")
    assert url is not None
    assert url.startswith("http")

  def testGetModelZipUrlNotFound(self):
    url = get_model_zip_url("nonexistent_model")
    assert url is None

  def testGetModelZipUrlFlexibleMatch(self):
    url = get_model_zip_url("CyberCab")
    assert url is not None

  def testDownloadInvalidModel(self):
    with pytest.raises(ValueError):
      download_tesla_images("nonexistent", "some_path", target_count=5)

"""
Tesla 图片下载工具
"""

import os
import zipfile
import io
from typing import Dict, List, Optional
import requests


TESLA_MODEL_MAP: Dict[str, str] = {
  "cybercab": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-cybercab.zip",
  "robovan": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-robovan.zip",
  "cybertruck": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-cybertruck.zip",
  "roadster": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-roadster.zip",
  "semi": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-semi.zip",
  "model-y": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-new-model-y.zip",
  "model-3": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-model-3-2024.zip",
  "model-s": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-model-s.zip",
  "model-x": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-model-x.zip",
  "model-3-performance": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-model-3-performance.zip",
  "group": "https://digitalassets.tesla.com/tesla-contents/raw/upload/tesla-gallery-group.zip",
}


def get_model_zip_url(model_name: str) -> Optional[str]:
  key = model_name.strip().lower().replace(" ", "-")
  return TESLA_MODEL_MAP.get(key) or TESLA_MODEL_MAP.get(
    model_name.strip().lower().replace(" ", "_")
  )


def download_tesla_images(model_name: str, save_path: str, target_count: int = 10) -> List[str]:
  zip_url = get_model_zip_url(model_name)
  if not zip_url:
    available = ", ".join(sorted(set(k for k in TESLA_MODEL_MAP if not k.startswith("model_"))))
    raise ValueError(f"不支持的车型: {model_name}，可用车型: {available}")

  model_key = model_name.strip().lower().replace(" ", "-")
  os.makedirs(save_path, exist_ok=True)
  headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
  }
  response = requests.get(zip_url, headers=headers, timeout=60)
  response.raise_for_status()

  saved_files = []
  with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
    image_files = sorted([
      f for f in zf.namelist()
      if not f.startswith("__MACOSX") and not os.path.basename(f).startswith(".")
         and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
    ])
    for idx, img_name in enumerate(image_files[:target_count]):
      ext = os.path.splitext(img_name)[1] or ".jpg"
      save_name = f"tesla_{model_key}_{idx + 1:02d}{ext}"
      save_path_full = os.path.join(save_path, save_name)
      zf.extract(img_name, save_path)
      extracted = os.path.join(save_path, img_name)
      if os.path.exists(extracted) and extracted != save_path_full:
        os.rename(extracted, save_path_full)
      saved_files.append(save_path_full)
  return saved_files

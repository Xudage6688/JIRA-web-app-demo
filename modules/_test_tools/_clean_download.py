"""
下载目录清理工具
"""

import os
from pathlib import Path
from typing import Dict, List


def clean_download_files(download_path: str, extensions: List[str]) -> Dict:
  deleted_count = 0
  failed_count = 0
  total_size = 0
  deleted_files = []
  failed_files = []

  for ext in extensions:
    ext = ext.strip().lower()
    for file_path in Path(download_path).iterdir():
      if not file_path.is_file():
        continue
      if file_path.suffix.lower() in [f".{e.strip().lower()}" for e in [ext]]:
        try:
          size = file_path.stat().st_size
          file_path.unlink()
          deleted_count += 1
          total_size += size
          deleted_files.append(file_path.name)
        except Exception as e:
          failed_count += 1
          failed_files.append({"file": file_path.name, "error": str(e)})

  return {
    "deleted_count": deleted_count,
    "failed_count": failed_count,
    "total_size": total_size,
    "deleted_files": deleted_files,
    "failed_files": failed_files,
  }


def format_size(size_bytes: int) -> str:
  for unit in ["B", "KB", "MB", "GB"]:
    if size_bytes < 1024:
      return f"{size_bytes:.2f} {unit}"
    size_bytes /= 1024
  return f"{size_bytes:.2f} TB"

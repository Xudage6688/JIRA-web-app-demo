"""
PDF 文件生成器 - 生成指定大小的 PDF 文件
"""

import os
from typing import List


def generate_minimal_pdf(target_size_mb: int = 5, file_count: int = 1, output_dir: str = ".") -> List[str]:
  os.makedirs(output_dir, exist_ok=True)
  target_bytes = int(target_size_mb * 1024 * 1024)
  generated_files = []

  for i in range(1, file_count + 1):
    filename = os.path.join(output_dir, f"large_file_{target_size_mb}m_{i:03d}.pdf")

    header = b"%PDF-1.4\n"

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = (
      b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 "
      b">>\nendobj\n"
    )
    page_content = b"q\nBT\n/F1 12 Tf\n100 700 Td\n(Test) Tj\nET\nQ\n"
    obj3 = (
      b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
      b"/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
      b"/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
    )
    obj4 = (
      b"4 0 obj\n<< /Length " + str(len(page_content)).encode() + b" >>\nstream\n"
      + page_content + b"\nendstream\nendobj\n"
    )

    body = obj1 + obj2 + obj3 + obj4
    xref_offset = len(header) + len(body)
    padding_needed = target_bytes - xref_offset - 100
    padding = b"0" * padding_needed if padding_needed > 0 else b""

    obj3_offset = len(header) + len(obj1) + len(obj2)
    obj4_offset = obj3_offset + len(obj3)
    body_start = obj4_offset + len(obj4)

    xref_lines = (
      f"{0:010d} 65535 f \n".encode() +
      f"{len(header):010d} 00000 n \n".encode() +
      f"{len(header)+len(obj1):010d} 00000 n \n".encode() +
      f"{obj3_offset:010d} 00000 n \n".encode()
    )
    xref = b"xref\n0 4\n" + xref_lines
    trailer = (
      b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
      b"startxref\n" + str(len(header) + len(body) + len(padding)).encode() + b"\n"
      b"%%EOF\n"
    )

    with open(filename, "wb") as f:
      f.write(header + body + padding + xref + trailer)

    generated_files.append(filename)

  return generated_files

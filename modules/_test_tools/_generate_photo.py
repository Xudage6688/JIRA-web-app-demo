"""
随机图片生成工具
"""

import os
import random
from typing import List
from PIL import Image, ImageDraw, ImageFont


def clear_output_directory(output_dir: str) -> None:
  if os.path.exists(output_dir):
    for f in os.listdir(output_dir):
      try:
        os.remove(os.path.join(output_dir, f))
      except OSError:
        pass


def generate_random_photos(num_photos: int, width: int, height: int, output_dir: str) -> List[str]:
  os.makedirs(output_dir, exist_ok=True)
  generated = []
  for i in range(1, num_photos + 1):
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    for x in range(width):
      for y in range(height):
        pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    filename = os.path.join(output_dir, f"random_{i:03d}.jpg")
    img.save(filename, 'JPEG')
    generated.append(filename)
  return generated


def generate_number_photos(num_photos: int, width: int, height: int, output_dir: str) -> List[str]:
  os.makedirs(output_dir, exist_ok=True)
  generated = []
  try:
    font = ImageFont.truetype("arial.ttf", size=max(width, height) // 2)
  except IOError:
    font = ImageFont.load_default()

  for i in range(1, num_photos + 1):
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    text = str(i)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill='black', font=font)
    filename = os.path.join(output_dir, f"number_{i:03d}.jpg")
    img.save(filename, 'JPEG')
    generated.append(filename)
  return generated

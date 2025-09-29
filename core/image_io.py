# core/image_io.py
from PIL import Image, ImageOps
import os

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

def is_image_file(path):
    _, ext = os.path.splitext(path.lower())
    return ext in SUPPORTED_EXTS

def open_image_fix_orientation(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # 修正 EXIF 方向
    return img

def generate_thumbnail(path, max_size=1024):
    img = open_image_fix_orientation(path)
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    return img  # PIL.Image instance

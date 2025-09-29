# core/exporter.py
from PIL import Image, ImageOps
import os
import json

def compose_watermark_on_image(
    src_path,
    dst_path,
    watermark_img,       # PIL.Image RGBA, 已按所需大小与旋转准备好
    anchor=(0.5,0.5),     # 归一化坐标 (0..1, 0左/0顶)
    output_format='png',  # 'png' or 'jpeg'
    jpeg_quality=90,
    resize_to=None        # (w,h) 或 None
):
    """
    把 watermark_img 合成到 src_path 上并保存。
    anchor 表示水印的中心点相对于目标图片左上角的位置（归一化）。
    watermark_img 应该是 RGBA，已包含需要的透明度与效果。
    """
    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img).convert('RGBA')

    if resize_to:
        img = img.resize(resize_to, Image.LANCZOS)

    iw, ih = img.size
    ww, wh = watermark_img.size

    # 计算水印放置左上角坐标（使 watermark 的中心位于 anchor 指定的点）
    center_x = int(anchor[0] * iw)
    center_y = int(anchor[1] * ih)

    left = center_x - ww // 2
    top = center_y - wh // 2

    # 创建叠加层
    layer = Image.new('RGBA', img.size, (0,0,0,0))
    layer.paste(watermark_img, (left, top), watermark_img)  # 使用 watermark 的 alpha 作为 mask

    composed = Image.alpha_composite(img, layer)  # RGBA

    if output_format.lower() in ('jpg', 'jpeg'):
        rgb = composed.convert('RGB')
        rgb.save(dst_path, 'JPEG', quality=jpeg_quality, optimize=True)
    else:
        composed.save(dst_path, 'PNG', compress_level=6)

    return dst_path

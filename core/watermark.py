# core/watermark.py
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

def create_text_watermark_image(
    text,
    font_path="C:\\code\\Photo_Watermark2\\resources\\华文中宋.ttf",
    font_size=64,
    color=(255,255,255,255),
    opacity=0.5,       # 0..1
    stroke_width=2,
    stroke_fill=(0,0,0,255),
    shadow_offset=(2,2),
    shadow_blur=4,
    max_width=None
):
    """
    返回一个透明背景的 RGBA Image，包含绘制好的文字（含描边和阴影）。
    font_path: 指向 ttf 文件的路径（若 None，Pillow 会尝试默认字体）
    color, stroke_fill: RGBA元组或RGB
    opacity: 文字主色的不透明度（0..1）
    """
    # 1. 载入字体
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # 临时画板测量
    dummy = Image.new("RGBA", (10,10), (0,0,0,0))
    draw = ImageDraw.Draw(dummy)

    # 允许换行或缩放以适配 max_width（可扩展）
    # 允许换行或缩放以适配 max_width（可扩展）
    bbox = draw.multiline_textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    # bbox = (left, top, right, bottom)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    canvas_w = w + abs(shadow_offset[0]) + stroke_width*4
    canvas_h = h + abs(shadow_offset[1]) + stroke_width*4

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0,0,0,0))
    draw = ImageDraw.Draw(canvas)

    # # 绘制阴影（在更大层上模糊）
    # if shadow_blur > 0:
    #     shadow_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
    #     sd = ImageDraw.Draw(shadow_layer)
    #     sx = stroke_width + max(0, shadow_offset[0])
    #     sy = stroke_width + max(0, shadow_offset[1])
    #     sd.text((sx, sy), text, font=font, fill=(*stroke_fill[:3], int(255*0.7)))
    #     shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    #     canvas = Image.alpha_composite(canvas, shadow_layer)
    #     draw = ImageDraw.Draw(canvas)
    
    pad = stroke_width   # 20% 字高作为 padding
    x = pad
    y = pad - int(font_size * 0.2)

    # 绘制阴影
    if shadow_blur > 0:
        shadow_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
        sd = ImageDraw.Draw(shadow_layer)
        sx = x + shadow_offset[0]
        sy = y + shadow_offset[1]
        sd.text((sx, sy), text, font=font, fill=(*stroke_fill[:3], int(255*0.7)))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
        canvas = Image.alpha_composite(canvas, shadow_layer)
        draw = ImageDraw.Draw(canvas)

    # # 描边（Pillow >= 8 支持 stroke_width）
    # x = stroke_width
    # y = stroke_width
    # fill_color = (*color[:3], int(255 * opacity))
    # draw.text((x, y), text, font=font, fill=fill_color, stroke_width=stroke_width, stroke_fill=stroke_fill)
    
    fill_color = (*color[:3], int(255 * opacity))
    draw.text((x, y), text, font=font, fill=fill_color, stroke_width=stroke_width, stroke_fill=stroke_fill)


    return canvas  # RGBA image

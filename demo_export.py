# demo_simple_export.py
from PIL import Image, ImageOps
from core.watermark import create_text_watermark_image
from core.exporter import compose_watermark_on_image

def demo():
    src = "example.jpg"   # 替换为你的图片
    dst = "out/example_watermarked.png"
    txt = "邹广文杰"

    # 生成高质量的水印图（比方说基于原图尺寸放大）
    base = Image.open(src)
    w, h = base.size

    # 假设想让文字宽度约为图片宽的 30%
    target_w = int(w * 0.3)
    # 先试一个 font_size 估算（粗略）
    font_size = int(target_w / max(len(txt), 6) * 1.2)

    wm = create_text_watermark_image(
        txt,
        font_path="C:\\code\\Photo_Watermark2\\resources\\华文中宋.ttf",
        font_size=500,
        color=(255,255,255,255),
        opacity=1,
        stroke_width=2,
        stroke_fill=(0,0,0,255),
        shadow_offset=(3,3),
        shadow_blur=3
    )

    # 可以缩放水印到更精确宽度
    ww, wh = wm.size
    scale = target_w / ww
    new_w = int(ww * scale)
    new_h = int(wh * scale)
    wm = wm.resize((new_w, new_h), Image.LANCZOS)

    compose_watermark_on_image(
        src_path=src,
        dst_path=dst,
        watermark_img=wm,
        anchor=(0.9,0.9),   # 右下角
        output_format='png'
    )
    print("Saved:", dst)

if __name__ == "__main__":
    demo()

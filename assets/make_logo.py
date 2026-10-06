"""Build the icon and logo PNGs from assets/icon-source.jpg.

Run with ``uv run python assets/make_logo.py``. The source is an original
AI-generated illustration (house outline around a PLC I/O module); it is not
affiliated with, or imitating, Siemens or Home Assistant branding.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
NAVY = (10, 52, 120)


def load_icon() -> Image.Image:
    """Cut the rounded tile out of its white JPG background."""
    img = Image.open(HERE / "icon-source.jpg").convert("RGBA")
    w, h = img.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(img, corner, (255, 255, 255, 0), thresh=40)
    img = img.crop(img.getchannel("A").point(lambda a: 255 if a > 0 else 0).getbbox())
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return square


def icon(size: int) -> Image.Image:
    return load_icon().resize((size, size), Image.LANCZOS)


def logo(height: int) -> Image.Image:
    ic = icon(height)
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(height * 0.42))
    except OSError:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(height * 0.42))
    text = "S7 PLC"
    gap = int(height * 0.12)
    box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    img = Image.new("RGBA", (height + gap + box[2] - box[0], height), (0, 0, 0, 0))
    img.paste(ic, (0, 0), ic)
    ImageDraw.Draw(img).text((height + gap - box[0], (height - (box[3] - box[1])) // 2 - box[1]), text, font=font, fill=NAVY)
    return img


if __name__ == "__main__":
    icon(256).save(HERE / "icon.png")
    icon(512).save(HERE / "icon@2x.png")
    logo(256).save(HERE / "logo.png")
    logo(512).save(HERE / "logo@2x.png")

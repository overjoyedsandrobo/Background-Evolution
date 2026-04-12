"""Generate a simple egg icon (PNG + ICO).

Usage:
    python tools/generate_icon.py
"""
from PIL import Image, ImageDraw
import os


def make_egg_icon(png_path="assets/icon.png", ico_path="assets/icon.ico", size=512):
    os.makedirs(os.path.dirname(png_path), exist_ok=True)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # egg body
    bbox = (int(size * 0.2), int(size * 0.12), int(size * 0.8), int(size * 0.88))
    draw.ellipse(bbox, fill=(245, 240, 220, 255))

    # highlight
    hbox = (int(size * 0.56), int(size * 0.18), int(size * 0.78), int(size * 0.34))
    draw.ellipse(hbox, fill=(255, 255, 255, 200))

    # save PNG (high-res source)
    img.save(png_path, format="PNG")

    # save ICO with multiple sizes
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)


if __name__ == "__main__":
    make_egg_icon()
    print("Generated assets/icon.png and assets/icon.ico")

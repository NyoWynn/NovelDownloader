"""
make_icon.py - Run once to convert the app logo PNG to .ico for PyInstaller.
"""

import os
import sys

from PIL import Image

png_path = os.path.join(os.path.dirname(__file__), "resources", "logo.png")
ico_path = os.path.join(os.path.dirname(__file__), "icon.ico")

if not os.path.exists(png_path):
    print(f"ERROR: {png_path} not found")
    sys.exit(1)

img = Image.open(png_path).convert("RGBA")
side = max(img.size)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
offset = ((side - img.width) // 2, (side - img.height) // 2)
square.paste(img, offset, img)
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

square.save(
    ico_path,
    format="ICO",
    sizes=sizes,
)
print(f"Icon saved to {ico_path}")

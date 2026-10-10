"""Generate/verify an asymmetric fixture, independently of the Swift processor.

Requires Pillow (included in the coordinator Python environment).
"""
from pathlib import Path
import sys
from PIL import Image

directory = Path(__file__).resolve().parents[1] / ".build"
directory.mkdir(exist_ok=True)
if sys.argv[1] == "fixture":
    image = Image.new("RGB", (256, 256))
    image.putdata([((x * 3 + y) % 256, (x + y * 7) % 256, (x * 11 + y * 5) % 256)
                   for y in range(256) for x in range(256)])
    image.save(directory / "input.png")
elif sys.argv[1] == "verify":
    source = Image.open(directory / "input.png").convert("RGB")
    output = Image.open(directory / "output.png").convert("RGB")
    assert source.size == output.size
    for y in range(256):
        for x in range(256):
            expected = (36, 203, 166) if x < 4 or y < 4 or x >= 252 or y >= 252 else source.getpixel((x, y))
            assert output.getpixel((x, y)) == expected, (x, y, output.getpixel((x, y)), expected)
    print("PASS: every interior RGB pixel preserved; all 4-pixel edges exactly (36,203,166)")
else:
    raise SystemExit("Use fixture or verify")

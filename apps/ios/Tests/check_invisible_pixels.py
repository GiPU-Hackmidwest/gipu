"""Check the staged V1 encoder independently with Pillow, using a compiled Swift harness.

Usage: python Tests/check_invisible_pixels.py .build/invisible-parity .build/invisible
The runtime finalizer remains legacy-framed until the coordinator rollout is confirmed.
"""
from pathlib import Path
import subprocess
import sys
from PIL import Image

binary = Path(sys.argv[1]).resolve()
directory = Path(sys.argv[2]).resolve()
directory.mkdir(parents=True, exist_ok=True)
for mode in ("RGB", "RGBA", "P"):
    image = Image.new("RGB", (256, 256))
    image.putdata([((x * 3 + y) % 256, (x + y * 7) % 256, (x * 11 + y * 5) % 256)
                   for y in range(256) for x in range(256)])
    if mode == "RGBA":
        image = image.convert("RGBA")
        image.putalpha(Image.frombytes("L", (256, 256), bytes((x * 5 + y * 3) % 256 for y in range(256) for x in range(256))))
    elif mode == "P":
        image = image.quantize(colors=128)
    source, output = directory / f"{mode}-input.png", directory / f"{mode}-output.png"
    image.save(source)
    subprocess.run([str(binary), str(source), str(output)], check=True)
    expected, actual = Image.open(source).convert("RGB"), Image.open(output).convert("RGB")
    assert expected.size == actual.size
    assert expected.tobytes() == actual.tobytes(), mode
    print(f"PASS: {mode} source, every one of 65,536 RGB pixels identical")

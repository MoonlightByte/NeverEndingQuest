"""Make desktop/build/icon.ico from dm_logo.png for the Windows installer (#1681).

Usage: python desktop/build-tools/make_icon.py [source.png] [target.ico]
Defaults: <repo>/dm_logo.png -> <repo>/desktop/build/icon.ico. Needs Pillow
(desktop/build-tools/requirements-icon.txt, hash-locked).
"""
import sys
from pathlib import Path

from PIL import Image

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main(argv):
    desktop = Path(__file__).resolve().parent.parent
    source = Path(argv[1]) if len(argv) > 1 else desktop.parent / "dm_logo.png"
    target = Path(argv[2]) if len(argv) > 2 else desktop / "build" / "icon.ico"
    with Image.open(source) as image:
        image = image.convert("RGBA")
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="ICO", sizes=SIZES)
    print(f"Wrote {target} ({len(SIZES)} sizes) from {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Generate transparent, multi-size Windows icons from the Flux mark."""
from pathlib import Path
from PIL import Image

def create_flux_icon():
    root = Path(__file__).resolve().parent.parent / "src" / "flux" / "static"
    image = Image.open(root / "flux-mark.png").convert("RGBA")
    sizes = [(s, s) for s in (256, 128, 64, 48, 32, 16)]
    for name in ("flux.ico", "flux-mark.ico"):
        target = root / name
        image.save(target, format="ICO", sizes=sizes)
        print(f"Saved {target}")

if __name__ == "__main__":
    create_flux_icon()
